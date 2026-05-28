from __future__ import annotations

import os

import requests

from src.ai.base import BaseAIProvider
from src.ai.json_utils import extract_json, normalize_analysis, normalize_batch_analysis
from src.ai.prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    build_batch_video_prompt,
    build_single_video_prompt,
)


VALID_OLLAMA_MODES = {"cloud_direct", "cloud_daemon", "local"}


class OllamaProvider(BaseAIProvider):
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        mode: str | None = None,
        api_key: str | None = None,
    ) -> None:
        resolved_mode = (mode or os.getenv("OLLAMA_MODE", "cloud_direct")).strip().lower()
        if resolved_mode not in VALID_OLLAMA_MODES:
            raise RuntimeError(
                "OLLAMA_MODE inválido. Use: cloud_direct, cloud_daemon ou local."
            )

        self.mode = resolved_mode
        self.api_key = (api_key or os.getenv("OLLAMA_API_KEY", "")).strip()
        model_name = (model or os.getenv("OLLAMA_MODEL", "gpt-oss:120b")).strip() or "gpt-oss:120b"

        default_base_url = self._default_base_url()
        resolved_base_url = (base_url or os.getenv("OLLAMA_BASE_URL", default_base_url)).strip()
        if not resolved_base_url:
            resolved_base_url = default_base_url

        if self.mode == "cloud_direct" and not self.api_key:
            raise RuntimeError(
                "Falta OLLAMA_API_KEY no arquivo .env para OLLAMA_MODE=cloud_direct"
            )

        if self.mode == "cloud_daemon" and not model_name.endswith("-cloud"):
            print(
                "[WARN] OLLAMA_MODE=cloud_daemon normalmente usa modelos com sufixo -cloud."
            )

        super().__init__(provider_name="ollama", model_name=model_name)
        self.base_url = resolved_base_url.rstrip("/")

    def _default_base_url(self) -> str:
        if self.mode == "cloud_direct":
            return "https://ollama.com"
        return "http://localhost:11434"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.mode == "cloud_direct":
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _connection_error_message(self) -> str:
        if self.mode == "cloud_daemon":
            return (
                "Ollama daemon não está disponível. Rode ollama signin, "
                "ollama pull <modelo-cloud> e mantenha o Ollama aberto."
            )

        if self.mode == "local":
            return "Ollama local não está disponível. Rode: ollama serve"

        return "Falha ao chamar Ollama Cloud."

    def _extract_response_text(self, data: dict) -> str:
        message = data.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content

        response_text = data.get("response")
        if isinstance(response_text, str) and response_text.strip():
            return response_text

        raise RuntimeError(
            "Resposta do Ollama não contém message.content nem response."
        )

    def _chat(self, prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2,
            },
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                headers=self._headers(),
                timeout=180,
            )
            response.raise_for_status()
        except requests.ConnectionError as exc:
            raise RuntimeError(self._connection_error_message()) from exc
        except requests.RequestException as exc:
            if self.mode == "cloud_direct":
                raise RuntimeError(f"Falha ao chamar Ollama Cloud: {exc}") from exc
            raise RuntimeError(self._connection_error_message()) from exc

        data = response.json()
        return self._extract_response_text(data)

    def analyze_video_opportunity(self, video: dict) -> dict:
        prompt = build_single_video_prompt(video)
        response_text = self._chat(prompt)
        parsed = extract_json(response_text)
        parsed["video_id"] = str(video.get("video_id", "")).strip()
        parsed["raw_json"] = response_text

        normalized = normalize_analysis(parsed)
        normalized["video_id"] = parsed["video_id"]
        normalized["raw_json"] = parsed["raw_json"]
        return normalized

    def analyze_video_opportunities_batch(self, videos: list[dict]) -> list[dict]:
        if not videos:
            return []

        prompt = build_batch_video_prompt(videos)
        response_text = self._chat(prompt)
        parsed = extract_json(response_text)
        analyses = normalize_batch_analysis(parsed, videos)

        for analysis in analyses:
            if not analysis.get("raw_json"):
                analysis["raw_json"] = response_text

        return analyses
