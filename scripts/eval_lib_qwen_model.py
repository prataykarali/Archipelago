"""Local lib-qwen extraction runner and response parser."""

from __future__ import annotations

import json
from pathlib import Path
import re
import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from okf.config import EXTRACTION_PROMPT_V15, MAX_CHARS_TO_SLM


def parse_json_array(raw: str):
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    a0, a1 = cleaned.find("["), cleaned.rfind("]")
    if a0 != -1 and a1 > a0:
        cleaned = cleaned[a0 : a1 + 1]
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            data = [data]
        if isinstance(data, list):
            return data, None
        return None, "not_list"
    except Exception as e:
        return None, str(e)


class LibQwenExtractor:
    def __init__(self, model_path: Path):
        print(f"Loading model from {model_path} ...")
        t0 = time.time()
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            dtype=dtype,
            device_map="auto" if torch.cuda.is_available() else None,
            trust_remote_code=True,
        )
        if not torch.cuda.is_available():
            self.model = self.model.to("cpu")
        self.model.eval()
        print(f"  loaded in {time.time() - t0:.1f}s  cuda={torch.cuda.is_available()}")

    def generate(self, prompt: str, max_new_tokens: int = 768) -> str:
        messages = [{"role": "user", "content": prompt}]
        try:
            templated = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            templated = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        inputs = self.tokenizer(templated, return_tensors="pt")
        device = next(self.model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            out = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                temperature=0.1,
            )
        gen = out[0][inputs["input_ids"].shape[1] :]
        return self.tokenizer.decode(gen, skip_special_tokens=True).strip()

    def extract_system_path(self, text: str) -> tuple[list | None, str, str | None]:
        """Same prompt path as okf.extraction.extract_okf_v15."""
        if len(text) > MAX_CHARS_TO_SLM:
            window = text[:MAX_CHARS_TO_SLM]
            cut = window.rfind("\n\n")
            if cut < MAX_CHARS_TO_SLM // 2:
                cut = max(window.rfind(". "), window.rfind("\n"))
            text = window[:cut] if cut > MAX_CHARS_TO_SLM // 2 else window
        prompt = EXTRACTION_PROMPT_V15.format(text=text)
        raw = self.generate(prompt)
        arr, err = parse_json_array(raw)
        return arr, raw, err
