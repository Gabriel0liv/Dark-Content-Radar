from __future__ import annotations

import json
import os

import requests

from src.ai.base import BaseAIProvider
from src.ai.json_utils import extract_json, normalize_analysis
from src.ai.prompts import ANALYSIS_SYSTEM_PROMPT, build_single_video_prompt


class GroqProvider(BaseAIProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        api_key = api_key or os.getenv("GROQ_API_KEY", "")
        model_name = model or os.getenv("GROQ_MODEL", "")
        if not api_key:
            raise RuntimeError("Falta GROQ_API_KEY no arquivo .env")
        if not model_name:
            raise RuntimeError("Falta GROQ_MODEL no arquivo .env")

        super().__init__(provider_name="groq", model_name=model_name)
        self.api_key = api_key

    def _sdk_client(self):
        try:
            from groq import Groq
        except ImportError:
            return None

        return Groq(api_key=self.api_key)

    def _requests_completion(
        self, prompt: str, use_response_format: bool = True
    ) -> dict:
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        if use_response_format:
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )

        if response.status_code >= 400 and use_response_format:
            return self._requests_completion(prompt, use_response_format=False)

        response.raise_for_status()
        return response.json()

    def analyze_video_opportunity(self, video: dict) -> dict:
        prompt = build_single_video_prompt(video)

        client = self._sdk_client()
        if client is not None:
            try:
                response = client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )
                content = response.choices[0].message.content
            except Exception:
                response = client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                )
                content = response.choices[0].message.content
        else:
            data = self._requests_completion(prompt)
            content = data["choices"][0]["message"]["content"]

        parsed = content if isinstance(content, dict) else extract_json(str(content))
        parsed["video_id"] = str(video.get("video_id", "")).strip()
        parsed["raw_json"] = json.dumps(parsed, ensure_ascii=False)
        normalized = normalize_analysis(parsed)
        normalized["video_id"] = parsed["video_id"]
        normalized["raw_json"] = parsed["raw_json"]
        return normalized
