import json
from typing import Any

try:
    from google import genai
except ImportError as exc:
    raise ImportError(
        "Pacote google-genai não encontrado na venv ativa. Rode: python -m pip install -U google-genai"
    ) from exc


VALID_LANGUAGES = {"pt", "en", "es", "unknown"}
VALID_DIFFICULTIES = {"low", "medium", "high"}
VALID_RISKS = {"low", "medium", "high"}


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "sim"}

    return bool(value)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [value] if value.strip() else []

        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]

    return []


def _build_prompt(video: dict) -> str:
    metadata = {
        "title": video.get("title", ""),
        "description": video.get("description", ""),
        "tags": _parse_tags(video.get("tags")),
        "category_id": video.get("category_id", ""),
        "default_language": video.get("default_language", ""),
        "default_audio_language": video.get("default_audio_language", ""),
        "channel_title": video.get("channel_title", ""),
        "niche": video.get("niche", ""),
        "keyword": video.get("keyword", ""),
        "views": video.get("views", 0),
        "views_per_day": video.get("views_per_day", 0),
        "comments": video.get("comments", 0),
        "duration_seconds": video.get("duration_seconds", 0),
        "url": video.get("url", ""),
    }

    return f"""
Você está avaliando se um vídeo do YouTube Shorts vale como referência estratégica para um canal dark em português (PT-BR/PT-PT).

Objetivo:
- analisar padrões, formato, gancho e oportunidade
- decidir se vale como referência para criar conteúdo original
- não clonar o vídeo
- não copiar o tema exato
- não sugerir plágio
- não depender de scraping, TikTok ou download do vídeo
- a análise é baseada apenas em metadados da YouTube Data API
- não afirme que você “viu” o vídeo
- você pode inferir formato provável, mas com cautela e deixando implícito que é uma inferência baseada em metadados

Regras obrigatórias:
- Responda apenas com JSON válido.
- Se o vídeo estiver em espanhol ou inglês, marque "is_good_reference" como false, exceto se o padrão for claramente adaptável para português.
- Se parecer gaming, fandom, trecho de série/filme, notícia política, produto/anúncio ou conteúdo dependente de imagem protegida, marque "is_good_reference" como false.
- Se for curiosidade genérica, insight, lista factual, psicologia, mistério, história, comportamento humano ou padrão adaptável para canal dark, pode marcar true.
- "original_angle_ideas" deve trazer apenas ângulos originais inspirados no padrão, nunca cópia do vídeo.
- "dark_channel_fit" é uma nota de 0 a 100.
- "production_difficulty" deve ser "low", "medium" ou "high".
- "copyright_risk" deve ser "low", "medium" ou "high".
- "reused_content_risk" deve ser "low", "medium" ou "high".
- "detected_language" deve ser "pt", "en", "es" ou "unknown".

Vídeo para análise:
{json.dumps(metadata, ensure_ascii=False, indent=2)}

Formato obrigatório:
{{
  "is_good_reference": true,
  "detected_language": "pt",
  "real_niche": "...",
  "content_type": "...",
  "hook_type": "...",
  "retention_pattern": "...",
  "dark_channel_fit": 85,
  "production_difficulty": "low",
  "copyright_risk": "low",
  "reused_content_risk": "low",
  "fact_check_needed": true,
  "opportunity_reason": "...",
  "original_angle_ideas": ["...", "...", "..."]
}}
""".strip()


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()

    if stripped.startswith("```"):
        parts = stripped.split("```")
        stripped = next((part for part in parts if "{" in part and "}" in part), stripped)
        stripped = stripped.replace("json", "", 1).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("Resposta do modelo não contém JSON válido.")

    return json.loads(stripped[start : end + 1])


def _response_to_dict(response: Any) -> dict[str, Any] | None:
    if isinstance(response, dict):
        return response

    to_json_dict = getattr(response, "to_json_dict", None)
    if callable(to_json_dict):
        data = to_json_dict()
        if isinstance(data, dict):
            return data

    return None


def _normalize_analysis(data: dict[str, Any]) -> dict[str, Any]:
    original_angles = data.get("original_angle_ideas", [])
    if not isinstance(original_angles, list):
        original_angles = []

    normalized = {
        "is_good_reference": _to_bool(data.get("is_good_reference", False)),
        "detected_language": str(data.get("detected_language", "unknown")).lower(),
        "real_niche": str(data.get("real_niche", "")).strip(),
        "content_type": str(data.get("content_type", "")).strip(),
        "hook_type": str(data.get("hook_type", "")).strip(),
        "retention_pattern": str(data.get("retention_pattern", "")).strip(),
        "dark_channel_fit": _to_int(data.get("dark_channel_fit", 0), default=0),
        "production_difficulty": str(data.get("production_difficulty", "medium")).lower(),
        "copyright_risk": str(data.get("copyright_risk", "medium")).lower(),
        "reused_content_risk": str(data.get("reused_content_risk", "medium")).lower(),
        "fact_check_needed": _to_bool(data.get("fact_check_needed", False)),
        "opportunity_reason": str(data.get("opportunity_reason", "")).strip(),
        "original_angle_ideas": [str(item).strip() for item in original_angles if str(item).strip()][:3],
    }

    if normalized["detected_language"] not in VALID_LANGUAGES:
        normalized["detected_language"] = "unknown"

    if normalized["production_difficulty"] not in VALID_DIFFICULTIES:
        normalized["production_difficulty"] = "medium"

    if normalized["copyright_risk"] not in VALID_RISKS:
        normalized["copyright_risk"] = "medium"

    if normalized["reused_content_risk"] not in VALID_RISKS:
        normalized["reused_content_risk"] = "medium"

    normalized["dark_channel_fit"] = max(0, min(100, normalized["dark_channel_fit"]))
    return normalized


def analyze_video_opportunity(api_key: str, model: str, video: dict) -> dict:
    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(video)

    response = None
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
            "model": model,
            "contents": prompt,
        }
        if config is not None:
            request_kwargs["config"] = config
        response = client.models.generate_content(**request_kwargs)
    except Exception:
        if config is None:
            raise
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )

    response_text = getattr(response, "text", "") or ""
    if response_text.strip():
        parsed = _extract_json(response_text)
    else:
        parsed = _response_to_dict(response)
        if parsed is None:
            parsed = _extract_json(json.dumps(response, default=str, ensure_ascii=False))
    normalized = _normalize_analysis(parsed)
    normalized["raw_json"] = json.dumps(parsed, ensure_ascii=False)
    return normalized
