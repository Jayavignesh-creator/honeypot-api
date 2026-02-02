import os

API_KEY = os.getenv("API_KEY", "dev-secret-key")
GUVI_CALLBACK_URL = os.getenv(
    "GUVI_CALLBACK_URL",
    "https://hackathon.guvi.in/api/updateHoneyPotFinalResult"
)
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "1800"))
MAX_REPLY_CHARS = int(os.getenv("MAX_REPLY_CHARS", "280"))
MODEL_PATH = os.getenv("MODEL_PATH", "./models/bert_scam_detector.pth")
