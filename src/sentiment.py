"""KR-FinBERT 호재·악재 판정 (FR-7)."""
from __future__ import annotations

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL_NAME = "snunlp/KR-FinBert-SC"
LABELS = {"positive": "호재", "neutral": "중립", "negative": "악재"}


class SentimentAnalyzer:
    def __init__(self, model_name: str = MODEL_NAME, local_files_only: bool = False):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=local_files_only)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name, local_files_only=local_files_only
        )
        self.model.eval()
        self.id2label = {i: LABELS[l.lower()] for i, l in self.model.config.id2label.items()}

    @torch.inference_mode()
    def predict(self, title: str, summary: str = "") -> tuple[str, float]:
        """(호재/중립/악재, 신뢰도 0~100). 입력은 제목 + 요약문."""
        text = f"{title}. {summary}".strip()
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        probs = torch.softmax(self.model(**inputs).logits[0], dim=-1)
        idx = int(probs.argmax())
        return self.id2label[idx], round(float(probs[idx]) * 100, 1)
