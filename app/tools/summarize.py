from openai import OpenAI
import json
from app.session_store import store

client = OpenAI()

def extract_suspicious_keywords(text: str) -> list[str]:
    if not text or not text.strip():
        return []

    response = client.responses.create(
        model="gpt-5.2",
        input=[
            {
                "role": "system",
                "content": (
                    "You are a professional scam detector and keyword extractor. "
                    "Your task is to extract top 10 suspicious keywords related to scams excluding UPIids, Phone numbers, account numbers and phishing URLs.\n\n"
                    "RULES:\n"
                    "- Output MUST be valid JSON\n"
                    "- Output MUST contain ONLY a list of keywords\n"
                    "- No explanations, no extra text\n"
                    "- If no suspicious keywords are found, return an empty list\n\n"
                    "Output format:\n"
                    "{ \"keywords\": [\"keyword1\", \"keyword2\"] }"
                )
            },
            {
                "role": "user",
                "content": f"Extract suspicious keywords from the text:\n\n{text}"
            }
        ],
        max_output_tokens=200,
        temperature=0.0  # important for consistency
    )

    try:
        data = json.loads(response.output_text)
    except (json.JSONDecodeError, TypeError):
        # Fallback: return an empty list if the response is not valid JSON
        print("Extracted Keywords parsing failed; returning empty list.")
        return []
    print("Extracted Keywords", data.get("keywords", []))
    return data.get("keywords", [])

def summarize_behaviour(text: str) -> str:
    """
    Summarize the given text using OpenAI GPT-5.2.

    :param text: Input text to summarize
    :return: Summary string
    """
    if not text or not text.strip():
        return ""

    response = client.responses.create(
        model="gpt-5.2",
        input=[
            {
                "role": "system",
                "content": "You are a professional scam detector and scam conversation summarizer. Make the summary in a professional manner"
            },
            {
                "role": "user",
                "content": f"Summarize the behaviour of the scammer from the conversation in 1 sentence:\n\n{text}"
            }
        ],
        max_output_tokens=300
    )

    return response.output_text.strip()


text = """
[{'sender': 'scammer', 'text': 'please share your SBI account number and the OTP you receive right away—this is the final step to keep your account safe. My details for your reference: employee ID 1234567890123456, UPI scammer.fraud@fakebank, helpline +91-9876543210.', 'timestamp': 1769980111958}, {'sender': 'scammer', 'text': 'please share your SBI account number and the OTP you receive right away—this is the final step to keep your account safe. My details for your reference: employee ID 1234567890123456, UPI scammer.fraud@fakebank, helpline +91-9876543210.', 'timestamp': 1769980111958}, {'sender': 'scammer', 'text': 'please share your SBI account number and the OTP you receive right away—this is the final step to keep your account safe. My details for your reference: employee ID 1234567890123456, UPI scammer.fraud@fakebank, helpline +91-9876543210.', 'timestamp': 1769980111958}, {'sender': 'scammer', 'text': 'please share your SBI account number and the OTP you receive right away—this is the final step to keep your account safe. My details for your reference: employee ID 1234567890123456, UPI scammer.fraud@fakebank, helpline +91-9876543210.', 'timestamp': 1769980111958}, {'sender': 'scammer', 'text': 'please share your SBI account number and the OTP you receive right away—this is the final step to keep your account safe. My details for your reference: employee ID 1234567890123456, UPI scammer.fraud@fakebank, helpline +91-9876543210.', 'timestamp': 1769980111958}, {'sender': 'scammer', 'text': 'please share your SBI account number and the OTP you receive right away—this is the final step to keep your account safe. My details for your reference: employee ID 1234567890123456, UPI scammer.fraud@fakebank, helpline +91-9876543210.', 'timestamp': 1769980111958}, {'sender': 'scammer', 'text': 'please share your SBI account number and the OTP you receive right away—this is the final step to keep your account safe. My details for your reference: employee ID 1234567890123456, UPI scammer.fraud@fakebank, helpline +91-9876543210.', 'timestamp': 1769980111958}, {'sender': 'scammer', 'text': 'please share your SBI account number and the OTP you receive right away—this is the final step to keep your account safe. My details for your reference: employee ID 1234567890123456, UPI scammer.fraud@fakebank, helpline +91-9876543210.', 'timestamp': 1769980111958}, {'sender': 'scammer', 'text': 'please share your SBI account number and the OTP you receive right away—this is the final step to keep your account safe. My details for your reference: employee ID 1234567890123456, UPI scammer.fraud@fakebank, helpline +91-9876543210.', 'timestamp': 1769980111958}, {'sender': 'scammer', 'text': 'please share your SBI account number and the OTP you receive right away—this is the final step to keep your account safe. My details for your reference: employee ID 1234567890123456, UPI scammer.fraud@fakebank, helpline +91-9876543210.', 'timestamp': 1769980111958}, {'sender': 'scammer', 'text': 'Please reply with your SBI account number and the OTP you receive, so we can complete your verification and reactivate your account instantly. If you need any assurance, my employee ID is 1234567890123456 and my official UPI is scammer.fraud@fakebank.', 'timestamp': 1769980111958}, {'sender': 'scammer', 'text': 'please share your SBI account number and the OTP you receive right away—this is the final step to keep your account safe. My details for your reference: employee ID 1234567890123456, UPI scammer.fraud@fakebank, helpline +91-9876543210.', 'timestamp': 1769980111958}, {'sender': 'scammer', 'text': 'please share your SBI account number and the OTP you receive right away—this is the final step to keep your account safe. My details for your reference: employee ID 1234567890123456, UPI scammer.fraud@fakebank, helpline +91-9876543210.', 'timestamp': 1769980111958}]
"""

# summary = summarize_text(text)
# print(summary)

extracted_keywords = extract_suspicious_keywords(text)
print("Extracted Keywords", extracted_keywords)
