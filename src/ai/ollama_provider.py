from __future__ import annotations

import json
import os

import requests

from src.ai.base import BaseAIProvider
from src.ai.json_utils import extract_json, normalize_analysis
from src.ai.prompts import ANALYSIS_SYSTEM_PROMPT, build_single_video_prompt


class OllamaProvider(BaseAIProvider):
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model_name = model or os.getenv("OLLAMA_MODEL", "qwen:latest")
        super().__init__(provider_name="ollama", model_name=model_name)
        self.base_url = base_url.rstrip("/")

    def _post_prompt(self, prompt: str) -> str:
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0.2},
                },
                timeout=120,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(
                "Ollama não está disponível. Rode: ollama serve"
            ) from exc

        data = response.json()
        return str(data.get("response", ""))

    def analyze_video_opportunity(self, video: dict) -> dict:
        prompt = build_single_video_prompt(video)
        response_text = self._post_prompt(prompt)
        parsed = extract_json(response_text)
        parsed["video_id"] = str(video.get("video_id", "")).strip()
        parsed["raw_json"] = json.dumps(parsed, ensure_ascii=False)
        normalized = normalize_analysis(parsed)
        normalized["video_id"] = parsed["video_id"]
        normalized["raw_json"] = parsed["raw_json"]
        return normalized
