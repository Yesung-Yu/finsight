"""KoBART 뉴스 요약 (FR-6)."""
from __future__ import annotations

import re

import torch
from transformers import BartForConditionalGeneration, PreTrainedTokenizerFast

MODEL_NAME = "gogamza/kobart-summarization"
MAX_INPUT_TOKENS = 1024  # KoBART 최대 입력 길이. 넘으면 앞부분만 사용
MAX_LINES = 3


class Summarizer:
    def __init__(self, model_name: str = MODEL_NAME, local_files_only: bool = False):
        self.tokenizer = PreTrainedTokenizerFast.from_pretrained(model_name, local_files_only=local_files_only)
        self.model = BartForConditionalGeneration.from_pretrained(model_name, local_files_only=local_files_only)
        self.model.eval()

    @torch.inference_mode()
    def summarize(self, text: str) -> str:
        """본문을 3줄 이내로 요약한다. 줄은 '\\n'으로 구분."""
        text = re.sub(r"\s+", " ", text or "").strip()
        if not text:
            return ""
        ids = self.tokenizer.encode(text)[: MAX_INPUT_TOKENS - 2]
        ids = [self.tokenizer.bos_token_id] + ids + [self.tokenizer.eos_token_id]
        out = self.model.generate(
            torch.tensor([ids]),
            max_length=160,
            min_length=20,
            num_beams=4,
            no_repeat_ngram_size=3,
            length_penalty=1.0,
            early_stopping=True,
        )
        summary = self.tokenizer.decode(out[0], skip_special_tokens=True).strip()
        return "\n".join(split_lines(summary)[:MAX_LINES])


def split_lines(text: str) -> list[str]:
    """요약문을 문장 단위로 나눈다. 같은 문장이 반복되면 한 번만 남긴다."""
    text = re.sub(r"(?<!\S)(\S+)(?: \1)+(?!\S)", r"\1", text)  # "3분기 3분기" 같은 연속 반복 제거
    sentences = re.split(r"(?<=[.?!])\s+|(?<=다\.)", text)
    lines, seen = [], set()
    for s in sentences:
        s = s.strip()
        if len(s) > 5 and s not in seen:
            seen.add(s)
            lines.append(s)
    return lines
