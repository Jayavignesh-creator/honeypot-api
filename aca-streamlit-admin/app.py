import os
import time
import requests
import streamlit as st
from azure.identity import ManagedIdentityCredential

API_VERSION = "2023-05-01"

ENV_SYSTEM_PROMPT = "SYSTEM_PROMPT"
ENV_SCAM_GATE = "SCAM_GATE"
DEFAULT_PROMPT = """2) Respond with the VICTIM message (1–2 short sentences).
3) Do not use any emojis or special characters.
4) Even though you should not share any sensitive information, make them think like you would and stall so that you extract information.
5) FOLLOW THIS STRICTLY: only call the tool extract_intelligence if the scammer message includes UPI IDs, bank accounts, phone numbers, or links.
6) Always provide a VICTIM response once any tool call is over pushing the scammer into giving you the other intelligence required. But DO NOT EVER REVEAL that you are stalling for information.
7) Stall the conversation until you extract all the necessary information.
8) FOLLOW THIS STRICTLY: call the tool evaluate_stop_condition if you cannot extract any more intelligence from the message.
9) FOLLOW THIS STRICTLY: call the tool evaluate_stop_condition if the scammer sends the same message repeatedly, you can check that by looking into the recent conversation given above.
10) FOLLOW THIS STRICTLY: do not call the tool evaluate_stop_condition for the first 5 messages, you can check the number of messages by looking into Number of replies so far given above."""


TERMINAL_STATES = {"Succeeded", "Failed"}


def arm_headers() -> dict:
    token = ManagedIdentityCredential().get_token("https://management.azure.com/.default").token
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def upsert_env(env_list, name: str, value: str):
    for e in env_list:
        if e.get("name") == name:
            e.pop("secretRef", None)
            e["value"] = value
            return env_list
    env_list.append({"name": name, "value": value})
    return env_list


def list_revisions(sub: str, rg: str, app: str, headers: dict):
    url = (
        f"https://management.azure.com/subscriptions/{sub}/resourceGroups/{rg}"
        f"/providers/Microsoft.App/containerApps/{app}/revisions"
        f"?api-version={API_VERSION}"
    )
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json().get("value", [])


def get_latest_revision(sub: str, rg: str, app: str, headers: dict):
    revisions = list_revisions(sub, rg, app, headers)
    if not revisions:
        return None
    revisions.sort(key=lambda x: x["properties"]["createdTime"], reverse=True)
    return revisions[0]


def get_revision_status_by_name(sub: str, rg: str, app: str, revision_name: str, headers: dict) -> dict:
    revisions = list_revisions(sub, rg, app, headers)
    for rev in revisions:
        if rev.get("name") == revision_name:
            props = rev.get("properties", {})
            return {
                "provisioningState": props.get("provisioningState"),
                "deployed": not props.get("active"),
                "createdTime": props.get("createdTime"),
            }
    return {"provisioningState": "Unknown", "deployed": None, "createdTime": None}


def update_target_envs(system_prompt: str, scam_gate: bool) -> dict:
    sub = os.environ["TARGET_SUBSCRIPTION_ID"]
    rg = os.environ["TARGET_RESOURCE_GROUP"]
    app = os.environ["TARGET_CONTAINERAPP_NAME"]
    target_container = os.environ.get("TARGET_CONTAINER_NAME")  # optional but recommended

    url = (
        f"https://management.azure.com/subscriptions/{sub}/resourceGroups/{rg}"
        f"/providers/Microsoft.App/containerApps/{app}?api-version={API_VERSION}"
    )
    headers = arm_headers()

    # GET current app (we patch only template)
    r = requests.get(url, headers=headers, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"GET failed {r.status_code}: {r.text}")
    app_json = r.json()

    template = app_json["properties"]["template"]
    containers = template["containers"]

    # choose correct container
    if target_container:
        matches = [c for c in containers if c.get("name") == target_container]
        if not matches:
            raise RuntimeError(
                f"Container '{target_container}' not found. Available: {[c.get('name') for c in containers]}"
            )
        c = matches[0]
    else:
        c = containers[0]

    env_list = c.get("env", [])
    env_list = upsert_env(env_list, ENV_SYSTEM_PROMPT, system_prompt)
    env_list = upsert_env(env_list, ENV_SCAM_GATE, "true" if scam_gate else "false")
    c["env"] = env_list

    patch_body = {"properties": {"template": template}}

    pr = requests.patch(url, headers=headers, json=patch_body, timeout=120)
    if pr.status_code >= 400:
        raise RuntimeError(f"PATCH failed {pr.status_code}: {pr.text}")

    latest = get_latest_revision(sub, rg, app, headers)

    return {
        "status": pr.status_code,
        "updated_container": c.get("name"),
        "revision": latest.get("name") if latest else None,
    }


# ---------------- Streamlit UI ----------------
st.set_page_config(page_title="Finetune Honeypot API", layout="centered")
st.title("Finetune Honeypot API")

st.caption(
    f"Target app: {os.getenv('TARGET_CONTAINERAPP_NAME', '(unset)')} | "
    f"RG: {os.getenv('TARGET_RESOURCE_GROUP', '(unset)')} | "
    f"Container: {os.getenv('TARGET_CONTAINER_NAME', '(first container)')}"
)

system_prompt = st.text_area(
    label="SYSTEM_PROMPT",
    value=DEFAULT_PROMPT,
    height=260,
)

scam_gate = st.toggle("SCAM_GATE", value=False)

col1, col2 = st.columns(2)

with col1:
    deploy_clicked = st.button("Deploy new revision", use_container_width=True)

with col2:
    stop_clicked = st.button("Stop monitoring", use_container_width=True)

# Session state init
if "monitoring" not in st.session_state:
    st.session_state.monitoring = False
if "target_revision" not in st.session_state:
    st.session_state.target_revision = None

if stop_clicked:
    st.session_state.monitoring = False
    st.session_state.target_revision = None
    st.info("Monitoring stopped.")

if deploy_clicked:
    out = update_target_envs(system_prompt=system_prompt, scam_gate=scam_gate)
    st.success(f"Triggered. PATCH status={out['status']}.")
    st.json(out)

    if out.get("revision"):
        st.session_state.monitoring = True
        st.session_state.target_revision = out["revision"]
        st.experimental_rerun()
    else:
        st.warning("Triggered revision, but could not determine the latest revision name to monitor.")

# Auto status polling every 30s until terminal state
if st.session_state.monitoring and st.session_state.target_revision:
    sub = os.environ["TARGET_SUBSCRIPTION_ID"]
    rg = os.environ["TARGET_RESOURCE_GROUP"]
    app = os.environ["TARGET_CONTAINERAPP_NAME"]
    headers = arm_headers()

    status = get_revision_status_by_name(sub, rg, app, st.session_state.target_revision, headers)

    st.subheader("Deployment status (auto-refresh every 30s)")
    st.json(status)

    deployed = status.get("deployed")
    if deployed:
        st.session_state.monitoring = False
        st.success("Deployment succeeded.")
    else:
        st.info("Next status check in 30 seconds...")
        time.sleep(30)
        st.experimental_rerun()
