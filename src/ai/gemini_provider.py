from __future__ import annotations

import json
import os
from typing import Any

from src.ai.base import BaseAIProvider
from src.ai.json_utils import extract_json, normalize_analysis
from src.ai.prompts import build_single_video_prompt


class GeminiProvider(BaseAIProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        model_name = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        if not api_key:
            raise RuntimeError("Falta GEMINI_API_KEY no arquivo .env")

        super().__init__(provider_name="gemini", model_name=model_name)
        self.api_key = api_key

    def _load_genai(self):
        try:
            from google import genai
        except ImportError as exc:
            raise ImportError(
                "Pacote google-genai não encontrado na venv ativa. Rode: python -m pip install -U google-genai"
            ) from exc

        return genai

    def _response_to_dict(self, response: Any) -> dict[str, Any] | None:
        if isinstance(response, dict):
            return response

        to_json_dict = getattr(response, "to_json_dict", None)
        if callable(to_json_dict):
            data = to_json_dict()
            if isinstance(data, dict):
                return data

        return None

    def analyze_video_opportunity(self, video: dict) -> dict:
        genai = self._load_genai()
        client = genai.Client(api_key=self.api_key)
        prompt = build_single_video_prompt(video)

        types_module = getattr(genai, "types", None)
        config = None
        if types_module is not None:
            generate_config = getattr(types_module, "GenerateContentConfig", None)
            if generate_config is not None:
                try:
                    config = generate_config(response_mime_type="application/json")
                except Exception:
                    config = None

        try:
            request_kwargs = {
                "model": self.model_name,
                "contents": prompt,
            }
            if config is not None:
                request_kwargs["config"] = config
            response = client.models.generate_content(**request_kwargs)
        except Exception:
            if config is None:
                raise
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )

        response_text = getattr(response, "text", "") or ""
        if response_text.strip():
            parsed = extract_json(response_text)
        else:
            parsed = self._response_to_dict(response)
            if parsed is None:
                parsed = extract_json(
                    json.dumps(response, default=str, ensure_ascii=False)
                )

        parsed["video_id"] = str(video.get("video_id", "")).strip()
        parsed["raw_json"] = json.dumps(parsed, ensure_ascii=False)
        normalized = normalize_analysis(parsed)
        normalized["video_id"] = parsed["video_id"]
        normalized["raw_json"] = parsed["raw_json"]
        return normalized
