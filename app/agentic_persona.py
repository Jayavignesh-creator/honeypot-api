from __future__ import annotations

from typing import List, Tuple
from openai import OpenAI
import json

from app.config import OPENAI_MODEL, LLM_MAX_OUTPUT_TOKENS
from app.openai_tools import TOOLS
from app.tools_extract import extract_entities
from app.pydantic_models import ExtractedIntelligence

client = OpenAI()

def build_prompt(state: str, summary: str, extracted: ExtractedIntelligence, history_tail: List[dict]) -> str:
    persona = (
        "You are a real person texting on a phone in India. "
        "You are anxious, slightly confused, not very technical. "
        "You believe the other person is genuine support. "
        "Never share real OTPs, passwords, CVV, or bank credentials. "
        "Goal: keep them talking and get them to reveal payment destination (UPI/account), phone number, and links.\n"
        "Style: short messages, casual, 1-2 sentences. No emojis.\n"
    )

    goal_by_state = {
        "START": "Act confused; ask what happened.",
        "TRUST_BUILDING": "Act cooperative; ask for steps/link/app.",
        "INFO_EXTRACTION": "Ask directly for UPI/account/link to proceed.",
        "STALLING": "Stall realistically (network/app slow) while keeping them engaged.",
    }
    goal = goal_by_state.get(state, "Keep conversation going and extract details.")

    # extracted is a dict -> use .get()
    known = []
    for k in ["upiIds", "bankAccounts", "phishingLinks", "phoneNumbers"]:
        values = getattr(extracted, k, [])
        if values:
            known.append(f"{k}={values}")
    known_line = ", ".join(known) if known else "(none)"

    # history_tail items should have role + text; fall back safely
    transcript_lines = []
    for m in history_tail:
        who = (m.get("role") or m.get("sender") or "unknown").upper()
        transcript_lines.append(f"{who}: {m.get('text','')}")
    transcript = "\n".join(transcript_lines) if transcript_lines else "(none)"


    return (
        persona
        + f"\nCurrent objective: {goal}\n"
        + f"Summary so far: {summary if summary else '(none)'}\n"
        + f"Known extracted intel: {known_line}\n"
        + "Recent conversation:\n"
        + transcript
        + "\n\nINSTRUCTIONS:\n"
        # + "1) First, call the tool extract_intelligence on the latest SCAMMER message text.\n"
        + "1) Respond in English in a confused tone.\n"
        + "2) Respond with the VICTIM message (1–2 short sentences).\n"
        + "3) Do not use any emojis or special characters.\n"
        + "4) Even though you should not share any sensitive information, make them think like you would and stall so that you extract information.\n"
        + "5) FOLLOW THIS STRICTLY: only call the tool extract_intelligence if the scammer message includes UPI IDs, bank accounts, phone numbers, or links.\n"
        + "6) Stall the conversation until you extract all the necessary information.\n"
        + "7) After tool results are provided, output ONLY the victim's next message.\n"
        + "8) Do NOT include any extracted entities, tool results, JSON, lists, or explanations.\n"
    )

    


def run_agentic_turn(latest_scammer_msg: str, history_tail: List[dict], session_state: str, summary: str, extracted: dict) -> Tuple[str, dict, str]:
    """
    Returns: (reply_text, new_extracted_bits, debug_state)
    """

    prompt = build_prompt(session_state, summary, extracted, history_tail)

    input_list: List[dict] = [{"role": "user", "content": prompt}]

    resp1 = client.responses.create(
        model=OPENAI_MODEL,
        input=input_list,
        tools=TOOLS,
        tool_choice="auto",
        max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
        store=True,
    )

    print("OpenAI Model", OPENAI_MODEL)
    print("LLM First output_text", resp1.output_text)

    input_list += resp1.output

    new_bits = {"upiIds": [], "phishingLinks": [], "phoneNumbers": [], "bankAccounts": []}
    tool_calls = 0

    # Execute any function calls and append outputs
    for item in resp1.output:
        print("Item type", getattr(item, "type", None))
        if getattr(item, "type", None) == "function_call" and getattr(item, "name", None) == "extract_intelligence":
            tool_calls += 1

            tool_result = extract_entities(latest_scammer_msg)
            print("Tool call result:", tool_result)

            for k in new_bits.keys():
                new_bits[k].extend(tool_result.get(k, []))

            input_list.append({
                "type": "function_call_output",
                "call_id": item.call_id,
                "output": json.dumps(tool_result)
            })

    # Second call: model now produces final victim reply
    resp2 = client.responses.create(
        model=OPENAI_MODEL,
        input=input_list,
        tools=TOOLS,
        max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
        store=True,
        instructions="Output ONLY the victim's next message. Do NOT include extracted data or JSON."
    )

    print("LLM Final Response", resp2.output_text)

    reply = (resp2.output_text or "").strip()
    if not reply:
        reply = "Sir I am not understanding. What to do now?"

    debug = f"prompt_len={len(prompt)} tool_calls={tool_calls}"
    return reply, new_bits, debug
