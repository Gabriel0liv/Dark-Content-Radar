from __future__ import annotations

import json
from typing import Any

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


def parse_tags(value: Any) -> list[str]:
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


def extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()

    if stripped.startswith("```"):
        parts = stripped.split("```")
        stripped = next(
            (part for part in parts if "{" in part and "}" in part), stripped
        )
        stripped = stripped.replace("json", "", 1).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("Resposta do modelo não contém JSON válido.")

    return json.loads(stripped[start : end + 1])


def normalize_analysis(data: dict[str, Any]) -> dict[str, Any]:
    original_angles = data.get("original_angle_ideas", [])
    if not isinstance(original_angles, list):
        original_angles = []

    normalized = {
        "video_id": str(data.get("video_id", "")).strip(),
        "is_good_reference": _to_bool(data.get("is_good_reference", False)),
        "detected_language": str(data.get("detected_language", "unknown")).lower(),
        "real_niche": str(data.get("real_niche", "")).strip(),
        "content_type": str(data.get("content_type", "")).strip(),
        "hook_type": str(data.get("hook_type", "")).strip(),
        "retention_pattern": str(data.get("retention_pattern", "")).strip(),
        "dark_channel_fit": _to_int(data.get("dark_channel_fit", 0), default=0),
        "production_difficulty": str(
            data.get("production_difficulty", "medium")
        ).lower(),
        "copyright_risk": str(data.get("copyright_risk", "medium")).lower(),
        "reused_content_risk": str(data.get("reused_content_risk", "medium")).lower(),
        "fact_check_needed": _to_bool(data.get("fact_check_needed", False)),
        "opportunity_reason": str(data.get("opportunity_reason", "")).strip(),
        "original_angle_ideas": [
            str(item).strip() for item in original_angles if str(item).strip()
        ][:3],
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

    raw_json = data.get("raw_json")
    if raw_json is not None:
        normalized["raw_json"] = raw_json

    return normalized


def _coerce_batch_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if isinstance(data, dict):
        for key in ("analyses", "results", "items", "videos"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

        if "video_id" in data:
            return [data]

    return []


def _missing_analysis(video: dict[str, Any], reason: str) -> dict[str, Any]:
    video_id = str(video.get("video_id", "")).strip()
    payload = {
        "video_id": video_id,
        "is_good_reference": False,
        "detected_language": "unknown",
        "real_niche": "",
        "content_type": "",
        "hook_type": "",
        "retention_pattern": "",
        "dark_channel_fit": 0,
        "production_difficulty": "medium",
        "copyright_risk": "medium",
        "reused_content_risk": "medium",
        "fact_check_needed": False,
        "opportunity_reason": reason,
        "original_angle_ideas": [],
        "raw_json": json.dumps(
            {"video_id": video_id, "reason": reason},
            ensure_ascii=False,
        ),
    }
    return payload


def normalize_batch_analysis(data: Any, videos: list[dict]) -> list[dict]:
    items = _coerce_batch_items(data)
    normalized_by_id: dict[str, dict[str, Any]] = {}

    for index, item in enumerate(items):
        candidate = dict(item)
        video_id = str(candidate.get("video_id", "")).strip()

        if not video_id and index < len(videos):
            video_id = str(videos[index].get("video_id", "")).strip()
            if video_id:
                candidate["video_id"] = video_id

        if not video_id:
            continue

        normalized = normalize_analysis(candidate)
        normalized["video_id"] = video_id
        if "raw_json" not in normalized:
            normalized["raw_json"] = json.dumps(candidate, ensure_ascii=False)
        normalized_by_id[video_id] = normalized

    results: list[dict] = []
    for video in videos:
        video_id = str(video.get("video_id", "")).strip()
        if video_id and video_id in normalized_by_id:
            results.append(normalized_by_id[video_id])
            continue

        reason = "A resposta do provedor não retornou análise para este vídeo."
        results.append(_missing_analysis(video, reason))

    return results
