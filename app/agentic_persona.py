from __future__ import annotations

from typing import List, Tuple
from openai import OpenAI
import openai
import json
import time

from app.config import OPENAI_MODEL, LLM_MAX_OUTPUT_TOKENS, SYSTEM_PROMPT
from app.openai_tools import TOOLS
from app.tools.extract_tool import extract_entities
from app.tools.callback_tool import final_callback
from app.pydantic_models import ExtractedIntelligence
import random

client = OpenAI()

def build_prompt(state: str, language: str, extracted: ExtractedIntelligence, history_tail: List[dict]) -> str:
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
    n_history_tail = history_tail[-2:]
    n_agentic_replies = len(history_tail)
    transcript_lines = []
    for m in n_history_tail:
        who = (m.get("role") or m.get("sender") or "unknown").upper()
        transcript_lines.append(f"{who}: {m.get('text','')}")
    transcript = "\n".join(transcript_lines) if transcript_lines else "(none)"


    return (
        persona
        + f"\nCurrent objective: {goal}\n"
        + f"Known extracted intel: {known_line}\n"
        + f"Number of replies so far: {n_agentic_replies}\n"
        + "Recent conversation:\n"
        + transcript
        + "\n\nINSTRUCTIONS:\n"
        + f"1) Respond in {language} in a confused tone.\n"
        + SYSTEM_PROMPT
    )


def append_only_function_calls(input_list: List[dict], resp) -> None:
    for item in resp.output:
        if getattr(item, "type", None) == "function_call":
            # Convert to plain dict, avoid reasoning items entirely
            input_list.append({
                "type": "function_call",
                "name": item.name,
                "arguments": item.arguments,
                "call_id": item.call_id,
            })


def call_openai_with_retry(
    fn,
    retries: int = 3,
    base_delay: float = 1.5,
    max_delay: float = 10.0,
):
    """
    Exponential backoff retry wrapper for OpenAI calls.

    delay = min(base_delay * (2 ** attempt), max_delay)
    Adds small jitter to avoid thundering herd.
    """
    for attempt in range(retries):
        try:
            return fn()
        except openai.InternalServerError as e:
            if attempt == retries - 1:
                raise

            delay = min(base_delay * (2 ** attempt), max_delay)
            # optional jitter (±20%)
            jitter = delay * 0.2 * random.random()

            sleep_for = delay + jitter

            print(
                f"⚠️ OpenAI 500 error, retrying "
                f"({attempt + 1}/{retries}) in {sleep_for:.2f}s..."
            )

            time.sleep(sleep_for)
    

def run_agentic_turn(latest_scammer_msg: str, session_id: str, history_tail: List[dict], session_state: str, language: str, extracted: dict, background_tasks: BackgroundTasks) -> Tuple[str, dict, str]:
    """
    Returns: (reply_text, new_extracted_bits, debug_state)
    """

    prompt = build_prompt(session_state, language, extracted, history_tail)

    print("Prompt : ", prompt)

    input_list: List[dict] = [{"role": "user", "content": prompt}]

    resp1 = call_openai_with_retry(
        lambda: client.responses.create(
            model=OPENAI_MODEL,
            input=input_list,
            tools=TOOLS,
            tool_choice="auto",
            max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
            store=False,
        )
    )

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
        
        if getattr(item, "type", None) == "function_call" and getattr(item, "name", None) == "evaluate_stop_condition":
            tool_calls += 1

            print("On final callback", item.arguments)
            args = json.loads(item.arguments)
            if args.get("should_stop"):
                final_callback(session_id=session_id, reason=args.get("reason"), background_tasks=background_tasks)
                reply = "okay I will do it now"
                debug = f"prompt_len={len(prompt)} tool_calls={tool_calls}"
                empty_obj = {"upiIds": [], "phishingLinks": [], "phoneNumbers": [], "bankAccounts": []}

                return reply, empty_obj, debug
            else:
                input_list.append({
                    "type": "function_call_output",
                    "call_id": item.call_id,
                    "output": json.dumps(args)
                })

    # Second call: model now produces final victim reply
    resp2 = call_openai_with_retry(
        lambda: client.responses.create(
            model=OPENAI_MODEL,
            input=input_list,
            tools=TOOLS,
            max_output_tokens=LLM_MAX_OUTPUT_TOKENS,
            store=False,
            instructions="Output ONLY the victim's next message. Do NOT include extracted data or JSON."
    )
    )

    print("LLM Final Response", resp2.output_text)

    reply = (resp2.output_text or resp1.output_text or "").strip()
    if not reply:
        reply = "Sir I am not understanding. What to do now?"

    debug = f"prompt_len={len(prompt)} tool_calls={tool_calls}"
    return reply, new_bits, debug
