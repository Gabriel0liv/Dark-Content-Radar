from __future__ import annotations

import json
import re
from typing import Iterable

from src.ai.constants import ANALYSIS_SCHEMA_VERSION
from src.ai.json_utils import normalize_analysis, parse_tags


SERIES_CLIP_MARKERS = {
    "s1e",
    "s2e",
    "episode",
    "temporada",
    "movie clip",
    "film clip",
    "netflix",
    "disney",
    "pixar",
    "the rookie",
    "dogman",
}
FANDOM_IP_MARKERS = {
    "pokemon",
    "pokémon",
    "marvel",
    "dc",
    "anime",
    "fandom",
}
PROMOTIONAL_MARKERS = {
    "sponsored",
    "promo",
    "buy",
    "discount",
    "download now",
    "ad",
    "qvc",
    "repairsme",
    "home repair",
}
PROMOTIONAL_APP_MARKERS = {
    "sponsored",
    "buy",
    "discount",
    "download now",
    "promo",
    "ad",
    "qvc",
    "repairsme",
    "home repair",
}
CELEBRITY_CONTEXT_MARKERS = {
    "selena quintanilla",
    "lupillo",
    "ángela aguilar",
    "angela aguilar",
}
BLOCKED_BRANDS = {
    "qvc",
    "repairsme",
}
SAFE_TECH_TERMS = {
    "chatgpt",
    "claude",
    "gemini",
    "automação",
    "automacao",
    "produtividade",
    "software",
    "ferramenta",
    "tool",
    "ia",
    "ai",
}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _contains_marker(text: str, marker: str) -> bool:
    if " " in marker:
        return marker in text
    return re.search(rf"(?<!\w){re.escape(marker)}(?!\w)", text) is not None


def _contains_any(text: str, markers: Iterable[str]) -> list[str]:
    return [marker for marker in markers if _contains_marker(text, marker)]


def _make_rejection(video: dict, *, reason: str, recommended_action: str, adaptation_type: str,
                    ip_risk: str = "medium", brand_or_product_risk: str = "medium",
                    source_dependency_risk: str = "medium", content_category: str = "other") -> dict:
    detected_language = str(
        video.get("default_language") or video.get("default_audio_language") or "unknown"
    ).lower().replace("_", "-")
    detected_language = detected_language.split("-", 1)[0]
    if detected_language not in {"pt", "en", "es"}:
        detected_language = "unknown"

    analysis = {
        "video_id": str(video.get("video_id", "")).strip(),
        "is_good_reference": False,
        "source_language": detected_language,
        "detected_language": detected_language,
        "target_market": "BR",
        "real_niche": str(video.get("niche", "")).strip(),
        "content_category": content_category,
        "content_type": "",
        "content_format": "clip" if recommended_action == "reject_ip_risk" else "unknown",
        "adaptation_type": adaptation_type,
        "hook_type": "",
        "retention_pattern": "",
        "dark_channel_fit": 0,
        "creator_fit_score": 0,
        "localization_potential": 0,
        "cultural_fit_br": 0,
        "evergreen_score": 20,
        "production_difficulty": "medium",
        "originality_requirement": "high",
        "copyright_risk": "medium",
        "reused_content_risk": "high",
        "source_dependency_risk": source_dependency_risk,
        "ip_risk": ip_risk,
        "brand_or_product_risk": brand_or_product_risk,
        "controversy_level": "low",
        "fact_check_needed": False,
        "recommended_action": recommended_action,
        "opportunity_reason": f"Descartado por filtro local: {reason}",
        "original_angle_ideas": [],
        "raw_json": json.dumps(
            {
                "video_id": video.get("video_id"),
                "source": "local-filter",
                "reason": reason,
            },
            ensure_ascii=False,
        ),
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
    }
    return normalize_analysis(analysis)


def local_pre_ai_filter(video: dict) -> dict | None:
    text_parts = [
        str(video.get("title", "")),
        str(video.get("description", "")),
        str(video.get("channel_title", "")),
        " ".join(parse_tags(video.get("tags"))),
    ]
    text = _normalize_text(" ".join(part for part in text_parts if part))
    if not text:
        return None

    series_markers = _contains_any(text, SERIES_CLIP_MARKERS)
    if series_markers:
        return _make_rejection(
            video,
            reason=f"conteúdo com forte sinal de série/filme/clip ({', '.join(series_markers[:3])})",
            recommended_action="reject_ip_risk",
            adaptation_type="high_ip_risk",
            ip_risk="high",
            source_dependency_risk="high",
            content_category="entertainment",
        )

    fandom_markers = _contains_any(text, FANDOM_IP_MARKERS)
    if fandom_markers:
        return _make_rejection(
            video,
            reason=f"conteúdo com forte dependência de fandom/IP ({', '.join(fandom_markers[:3])})",
            recommended_action="reject_ip_risk",
            adaptation_type="high_ip_risk",
            ip_risk="high",
            source_dependency_risk="high",
            content_category="fandom_ip",
        )

    celebrity_markers = _contains_any(text, CELEBRITY_CONTEXT_MARKERS)
    if celebrity_markers:
        return _make_rejection(
            video,
            reason=f"fofoca/celebridade estrangeira excessivamente contextual ({', '.join(celebrity_markers[:2])})",
            recommended_action="reject_too_contextual",
            adaptation_type="source_too_contextual",
            source_dependency_risk="high",
            content_category="entertainment",
        )

    promo_markers = _contains_any(text, PROMOTIONAL_MARKERS)
    has_brand = any(_contains_marker(text, brand) for brand in BLOCKED_BRANDS)
    mentions_app = _contains_marker(text, "app")
    safe_tech_context = any(_contains_marker(text, term) for term in SAFE_TECH_TERMS)
    app_is_promotional = mentions_app and (
        bool(_contains_any(text, PROMOTIONAL_APP_MARKERS)) or has_brand
    )

    if promo_markers or app_is_promotional:
        if not safe_tech_context or app_is_promotional or has_brand:
            reason_markers = promo_markers[:3] or ["app promocional"]
            return _make_rejection(
                video,
                reason=f"conteúdo com cara de anúncio/promoção ({', '.join(reason_markers)})",
                recommended_action="reject_promotional",
                adaptation_type="promotional",
                brand_or_product_risk="high",
                source_dependency_risk="medium",
                content_category="product",
            )

    return None
