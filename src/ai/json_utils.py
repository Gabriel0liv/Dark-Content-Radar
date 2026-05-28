from __future__ import annotations

import json
from typing import Any

VALID_LANGUAGES = {"pt", "en", "es", "unknown"}
VALID_DIFFICULTIES = {"low", "medium", "high"}
VALID_RISKS = {"low", "medium", "high"}
VALID_TARGET_MARKETS = {"BR", "PT", "global_pt"}
VALID_CONTENT_CATEGORIES = {
    "curiosity",
    "ai_tech",
    "science",
    "psychology",
    "history",
    "mystery",
    "finance",
    "controversy",
    "news",
    "entertainment",
    "product",
    "fandom_ip",
    "other",
}
VALID_CONTENT_FORMATS = {
    "short_explainer",
    "list",
    "story",
    "news_commentary",
    "tutorial",
    "reaction",
    "essay",
    "clip",
    "ad",
    "unknown",
}
VALID_ADAPTATION_TYPES = {
    "original_pt",
    "foreign_adaptable",
    "foreign_not_adaptable",
    "global_trend",
    "local_brazil_trend",
    "source_too_contextual",
    "high_ip_risk",
    "promotional",
    "reject",
}
VALID_REQUIREMENTS = {"low", "medium", "high"}
VALID_CONTROVERSY = {"low", "medium", "high"}
VALID_RECOMMENDED_ACTIONS = {
    "use_as_reference",
    "adapt_with_research",
    "reject_ip_risk",
    "reject_too_contextual",
    "reject_promotional",
    "reject_low_relevance",
    "reject_low_quality",
    "needs_manual_review",
}


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


def _clamp_score(value: Any, default: int = 0) -> int:
    return max(0, min(100, _to_int(value, default=default)))


def _normalize_language(value: Any) -> str:
    normalized = str(value or "").lower().strip().replace("_", "-")
    if not normalized:
        return ""

    prefix = normalized.split("-", 1)[0]
    if prefix in VALID_LANGUAGES:
        return prefix

    return "unknown"


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

    source_language = _normalize_language(data.get("source_language", ""))
    detected_language = _normalize_language(data.get("detected_language", ""))
    if not source_language and detected_language:
        source_language = detected_language
    if not detected_language and source_language:
        detected_language = source_language
    if source_language not in VALID_LANGUAGES:
        source_language = "unknown"
    if detected_language not in VALID_LANGUAGES:
        detected_language = source_language if source_language in VALID_LANGUAGES else "unknown"

    dark_channel_fit = _clamp_score(data.get("dark_channel_fit", 0), default=0)
    creator_fit_score = data.get("creator_fit_score", data.get("dark_channel_fit", 0))

    normalized = {
        "video_id": str(data.get("video_id", "")).strip(),
        "is_good_reference": _to_bool(data.get("is_good_reference", False)),
        "source_language": source_language,
        "detected_language": detected_language,
        "target_market": str(data.get("target_market", "BR")).strip() or "BR",
        "real_niche": str(data.get("real_niche", "")).strip(),
        "content_category": str(data.get("content_category", "other")).lower().strip(),
        "content_type": str(data.get("content_type", "")).strip(),
        "content_format": str(data.get("content_format", "unknown")).lower().strip(),
        "adaptation_type": str(data.get("adaptation_type", "reject")).lower().strip(),
        "hook_type": str(data.get("hook_type", "")).strip(),
        "retention_pattern": str(data.get("retention_pattern", "")).strip(),
        "dark_channel_fit": dark_channel_fit,
        "creator_fit_score": _clamp_score(creator_fit_score, default=dark_channel_fit),
        "localization_potential": _clamp_score(data.get("localization_potential", 0), default=0),
        "cultural_fit_br": _clamp_score(data.get("cultural_fit_br", 0), default=0),
        "evergreen_score": _clamp_score(data.get("evergreen_score", 50), default=50),
        "production_difficulty": str(
            data.get("production_difficulty", "medium")
        ).lower(),
        "originality_requirement": str(data.get("originality_requirement", "medium")).lower().strip(),
        "copyright_risk": str(data.get("copyright_risk", "medium")).lower(),
        "reused_content_risk": str(data.get("reused_content_risk", "medium")).lower(),
        "source_dependency_risk": str(data.get("source_dependency_risk", "medium")).lower().strip(),
        "ip_risk": str(data.get("ip_risk", "medium")).lower().strip(),
        "brand_or_product_risk": str(data.get("brand_or_product_risk", "medium")).lower().strip(),
        "controversy_level": str(data.get("controversy_level", "low")).lower().strip(),
        "fact_check_needed": _to_bool(data.get("fact_check_needed", False)),
        "recommended_action": str(data.get("recommended_action", "needs_manual_review")).lower().strip(),
        "opportunity_reason": str(data.get("opportunity_reason", "")).strip(),
        "original_angle_ideas": [
            str(item).strip() for item in original_angles if str(item).strip()
        ][:3],
        "analysis_schema_version": _to_int(data.get("analysis_schema_version", 1), default=1),
    }

    if normalized["production_difficulty"] not in VALID_DIFFICULTIES:
        normalized["production_difficulty"] = "medium"

    if normalized["copyright_risk"] not in VALID_RISKS:
        normalized["copyright_risk"] = "medium"

    if normalized["reused_content_risk"] not in VALID_RISKS:
        normalized["reused_content_risk"] = "medium"

    if normalized["target_market"] not in VALID_TARGET_MARKETS:
        normalized["target_market"] = "BR"
    if normalized["content_category"] not in VALID_CONTENT_CATEGORIES:
        normalized["content_category"] = "other"
    if normalized["content_format"] not in VALID_CONTENT_FORMATS:
        normalized["content_format"] = "unknown"
    if normalized["adaptation_type"] not in VALID_ADAPTATION_TYPES:
        normalized["adaptation_type"] = "reject"
    if normalized["originality_requirement"] not in VALID_REQUIREMENTS:
        normalized["originality_requirement"] = "medium"
    if normalized["source_dependency_risk"] not in VALID_RISKS:
        normalized["source_dependency_risk"] = "medium"
    if normalized["ip_risk"] not in VALID_RISKS:
        normalized["ip_risk"] = "medium"
    if normalized["brand_or_product_risk"] not in VALID_RISKS:
        normalized["brand_or_product_risk"] = "medium"
    if normalized["controversy_level"] not in VALID_CONTROVERSY:
        normalized["controversy_level"] = "low"
    if normalized["recommended_action"] not in VALID_RECOMMENDED_ACTIONS:
        normalized["recommended_action"] = "needs_manual_review"

    if normalized["recommended_action"].startswith("reject_"):
        normalized["is_good_reference"] = False
    elif normalized["adaptation_type"] == "high_ip_risk":
        normalized["is_good_reference"] = False
    elif normalized["ip_risk"] == "high":
        normalized["is_good_reference"] = False
    elif normalized["reused_content_risk"] == "high":
        normalized["is_good_reference"] = False
    elif normalized["brand_or_product_risk"] == "high":
        normalized["is_good_reference"] = False
    elif normalized["recommended_action"] in {"use_as_reference", "adapt_with_research"}:
        normalized["is_good_reference"] = True

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
        "source_language": "unknown",
        "detected_language": "unknown",
        "target_market": "BR",
        "real_niche": "",
        "content_category": "other",
        "content_type": "",
        "content_format": "unknown",
        "adaptation_type": "reject",
        "hook_type": "",
        "retention_pattern": "",
        "dark_channel_fit": 0,
        "creator_fit_score": 0,
        "localization_potential": 0,
        "cultural_fit_br": 0,
        "evergreen_score": 50,
        "production_difficulty": "medium",
        "originality_requirement": "medium",
        "copyright_risk": "medium",
        "reused_content_risk": "medium",
        "source_dependency_risk": "medium",
        "ip_risk": "medium",
        "brand_or_product_risk": "medium",
        "controversy_level": "low",
        "fact_check_needed": False,
        "recommended_action": "needs_manual_review",
        "opportunity_reason": reason,
        "original_angle_ideas": [],
        "raw_json": json.dumps(
            {"video_id": video_id, "reason": reason},
            ensure_ascii=False,
        ),
    }
    return normalize_analysis(payload)


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
