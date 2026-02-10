import os
import requests
import streamlit as st
from azure.identity import ManagedIdentityCredential

API_VERSION = "2023-05-01"
ENV_SYSTEM_PROMPT = "SYSTEM_PROMPT"
ENV_SCAM_GATE = "SCAM_GATE"

def arm_headers():
    token = ManagedIdentityCredential().get_token("https://management.azure.com/.default").token
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def upsert_env(env_list, name, value: str):
    for e in env_list:
        if e.get("name") == name:
            e.pop("secretRef", None)
            e["value"] = value
            return env_list
    env_list.append({"name": name, "value": value})
    return env_list

def update_target_envs(system_prompt: str, scam_gate: bool):
    sub = os.environ["TARGET_SUBSCRIPTION_ID"]
    rg = os.environ["TARGET_RESOURCE_GROUP"]
    app = os.environ["TARGET_CONTAINERAPP_NAME"]
    target_container = os.environ.get("TARGET_CONTAINER_NAME")  # recommended

    url = (
        f"https://management.azure.com/subscriptions/{sub}/resourceGroups/{rg}"
        f"/providers/Microsoft.App/containerApps/{app}?api-version={API_VERSION}"
    )
    headers = arm_headers()

    # GET current app
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

    # PATCH only template (avoids registry secret issues)
    patch_body = {"properties": {"template": template}}
    pr = requests.patch(url, headers=headers, json=patch_body, timeout=120)

    if pr.status_code >= 400:
        raise RuntimeError(f"PATCH failed {pr.status_code}: {pr.text}")

    # ARM often returns 204 No Content
    return {"status": pr.status_code, "updated_container": c.get("name")}

# ---------------- Streamlit UI ----------------
st.title("Finetune Honeypot API")

system_prompt = st.text_area(
    label="SYSTEM_PROMPT",
    height=260,
    placeholder="Paste the prompt here...",
)

scam_gate = st.toggle("SCAM_GATE", value=True)

if st.button("Deploy new revision"):
    out = update_target_envs(system_prompt=system_prompt, scam_gate=scam_gate)
    st.success(f"Updated. PATCH status={out['status']}. New revision should be created.")
    st.json(out)
