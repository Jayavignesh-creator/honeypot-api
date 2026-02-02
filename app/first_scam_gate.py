from __future__ import annotations

import os
from typing import Dict, Any, Optional

import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModel

class BERTScamClassifier(nn.Module):
    def __init__(
        self,
        model_name: str = "bert-base-multilingual-cased",
        n_classes: int = 2,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(self.bert.config.hidden_size, n_classes)

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )

        pooled_output = outputs.pooler_output
        output = self.dropout(pooled_output)
        logits = self.classifier(output)
        return logits


class FirstLayerScamDetector:
    def __init__(self, device: Optional[str] = None):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "mps"
        self.device = torch.device(device)

        self.model: Optional[BERTScamClassifier] = None
        self.tokenizer: Optional[AutoTokenizer] = None

        self.model_name = "bert-base-multilingual-cased"
        self.max_length = 128
        self.id2label = {0: "trust", 1: "scam"}

    def load_model(self, model_path):
        try:
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model file not found: {model_path}")

            checkpoint = torch.load(model_path, map_location="cpu")

            model_name = checkpoint.get("model_name", "bert-base-multilingual-cased")
            self.max_length = int(checkpoint.get("max_length", 128))

            raw_id2label = checkpoint.get("id2label", {0: "trust", 1: "scam"})
            self.id2label = {int(k): v for k, v in raw_id2label.items()}

            self.tokenizer = AutoTokenizer.from_pretrained(model_name)

            self.model = BERTScamClassifier(model_name=model_name, n_classes=len(self.id2label), dropout=0.3)

            missing, unexpected = self.model.load_state_dict(checkpoint["model_state_dict"], strict=False)

            if unexpected:
                print("Ignored unexpected keys (OK):", unexpected[:10], "..." if len(unexpected) > 10 else "")
            if missing:
                print("Missing keys (check if serious):", missing[:10], "..." if len(missing) > 10 else "")

            if torch.cuda.is_available():
                self.device = torch.device("cuda")
            else:
                self.device = torch.device("cpu")

            self.model.to(self.device)
            self.model.eval()

            print(f"Model loaded successfully! device={self.device}, model={model_name}")
            return True

        except Exception as e:
            print(f"Error loading model: {e}")
            return False


    @torch.no_grad()
    def predict_message(
        self,
        message: str,
        threshold: float = 0.45,
    ) -> Dict[str, Any]:
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        if not message or not message.strip():
            return {
                "prediction": "No prediction",
                "is_scam": False,
                "confidence": 0.0,
                "p_trust": 0.0,
                "p_scam": 0.0,
            }

        message = message.strip()

        encoding = self.tokenizer(
            message,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )

        input_ids = encoding["input_ids"].to(self.device)
        attention_mask = encoding["attention_mask"].to(self.device)

        logits = self.model(input_ids, attention_mask)
        probs = torch.softmax(logits, dim=1)[0]

        p_trust = float(probs[0].item())
        p_scam = float(probs[1].item())

        is_scam = p_scam >= threshold
        pred_idx = 1 if is_scam else 0

        return {
            "prediction": self.id2label[pred_idx],
            "is_scam": bool(is_scam),
            "confidence": round(p_scam if is_scam else p_trust, 4),
            "p_trust": round(p_trust, 4),
            "p_scam": round(p_scam, 4),
        }


# ======================================================
# CLI test (optional)
# ======================================================
if __name__ == "__main__":
    msg = "URGENT: Your SBI account has been compromised. Your account will be blocked in 2 hours. Share your account number and OTP immediately to verify your identity."

    detector = FirstLayerScamDetector()
    if not detector.load_model("./models/bert_scam_detector.pth"):
        raise SystemExit(2)

    print(detector.predict_message(msg))
