import os

# API Config
API_KEY = os.getenv("API_KEY", "dev-secret-key")
GUVI_CALLBACK_URL = os.getenv("GUVI_CALLBACK_URL")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "1800"))
MAX_REPLY_CHARS = int(os.getenv("MAX_REPLY_CHARS", "280"))
MODEL_PATH = os.getenv("MODEL_PATH", "./models/bert_scam_detector.pth")

# OpenAI config
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
LLM_MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "120"))