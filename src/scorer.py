import math
import os
import re
import unicodedata
from datetime import datetime, timezone

MIN_VIEWS = 10000
MIN_VIEWS_PER_DAY = 5000

DARK_FRIENDLY_WORDS = [
    "mistério",
    "misterio",
    "segredo",
    "obscuro",
    "assustador",
    "estranho",
    "bizarro",
    "ninguém sabe",
    "ninguem sabe",
    "experimento",
    "psicologia",
    "cérebro",
    "cerebro",
    "verdade",
    "erro",
    "proibido",
    "história real",
    "historia real",
    "curiosidade",
    "fato",
    "fatos",
]

BLOCKED_WORDS = [
    "globonews",
    "lula",
    "bolsonaro",
    "trump",
    "biden",
    "gobierno",
    "cosas",
    "extrañas",
    "raras",
    "news",
    "noticias",
    "política",
    "politica",
    "gaming",
    "gameplay",
    "video game",
    "videogame",
    "minecraft",
    "roblox",
    "among us",
    "fnaf",
    "poppyplaytime",
    "warhammer",
    "space marine",
    "qvc",
    "instaseal",
    "graduation",
    "psychology facts",
    "your body",
    "produto",
    "produtos",
    "product",
    "products",
    "anúncio",
    "anuncio",
    "promoção",
    "promocao",
    "review",
    "unboxing",
    "ad",
    "sponsored",
]

SPANISH_STRONG_TERMS = [
    "¿",
    "¡",
    "qué",
    "pasaría",
    "pudieras",
    "engañará",
    "aprendió",
    "cerebro humano",
    "su cerebro",
    "esta ilusión",
    "el detalle",
    "la mente",
    "datos curiosos",
    "curiosidadeshistoricas",
]

ENGLISH_STRONG_TERMS = [
    "the psychology",
    "behind",
    "during movies",
    "the bizarre",
    "ancient story",
    "your body",
    "if you have",
    "actually too expensive",
]

NICHE_WORDS = {
    "História sombria": [
        "história",
        "historia",
        "histórico",
        "historico",
        "antigo",
        "medieval",
        "império",
        "imperio",
        "guerra",
        "rei",
        "rainha",
        "arqueologia",
        "civilização",
        "civilizacao",
    ],
    "Psicologia": [
        "psicologia",
        "psicológico",
        "psicologico",
        "mente",
        "cérebro",
        "cerebro",
        "comportamento",
        "humano",
        "emocional",
        "cognitivo",
        "pensamento",
    ],
    "Mistérios reais": [
        "mistério",
        "misterio",
        "inexplicável",
        "inexplicavel",
        "caso",
        "casos",
        "estranho",
        "estranhos",
        "real",
        "reais",
        "desaparecimento",
        "segredo",
    ],
    "IA e tecnologia": [
        "ia",
        "inteligência artificial",
        "inteligencia artificial",
        "chatgpt",
        "automação",
        "automacao",
        "tecnologia",
        "ferramenta",
        "app",
        "apps",
        "software",
        "produtividade",
    ],
    "Finanças básicas": [
        "finanças",
        "financas",
        "financeiro",
        "economizar",
        "economia",
        "dinheiro",
        "cartão",
        "cartao",
        "poupança",
        "poupanca",
        "educação financeira",
        "educacao financeira",
    ],
}


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "sim", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def get_viral_config() -> dict:
    acceptance_mode = os.getenv("VIRAL_ACCEPTANCE_MODE", "or").strip().lower()
    if acceptance_mode not in {"or", "and"}:
        acceptance_mode = "or"

    return {
        "viral_only": _env_bool("VIRAL_ONLY", True),
        "viral_acceptance_mode": acceptance_mode,
        "min_total_views": _env_int("MIN_TOTAL_VIEWS", 1_000_000),
        "min_views_per_day": _env_int("MIN_VIEWS_PER_DAY", 100_000),
        "min_rising_total_views": _env_int("MIN_RISING_TOTAL_VIEWS", 300_000),
        "min_rising_views_per_day": _env_int("MIN_RISING_VIEWS_PER_DAY", 50_000),
        "min_opportunity_score": _env_int("MIN_OPPORTUNITY_SCORE", 70),
        "viral_strict_mode": _env_bool("VIRAL_STRICT_MODE", False),
    }


def _passes_viral_acceptance(views: int, views_per_day: float, config: dict) -> bool:
    has_total_views = views >= config["min_total_views"]
    has_views_per_day = views_per_day >= config["min_views_per_day"]

    if config["viral_acceptance_mode"] == "and":
        return has_total_views and has_views_per_day

    return has_total_views or has_views_per_day


def _passes_rising_acceptance(views: int, views_per_day: float, config: dict) -> bool:
    return (
        views >= config["min_rising_total_views"]
        or views_per_day >= config["min_rising_views_per_day"]
    )


def classify_viral_tier(views: int, views_per_day: float, config: dict | None = None) -> str:
    config = config or get_viral_config()

    if views >= 5_000_000 or views_per_day >= 500_000:
        return "mega_viral"
    if _passes_viral_acceptance(views, views_per_day, config):
        return "viral"
    if _passes_rising_acceptance(views, views_per_day, config):
        return "rising"
    return "weak"


def is_accepted_by_viral_mode(views: int, views_per_day: float, config: dict) -> bool:
    viral_tier = classify_viral_tier(views, views_per_day, config)
    if not config["viral_only"]:
        return True
    if viral_tier in {"mega_viral", "viral"}:
        return True
    return viral_tier == "rising" and not config["viral_strict_mode"]


def is_candidate_by_viral_tier(viral_tier: str, config: dict) -> bool:
    if viral_tier in {"mega_viral", "viral"}:
        return True
    return viral_tier == "rising" and not config["viral_strict_mode"]


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return re.sub(r"\s+", " ", normalized).strip()


def _contains_term(text: str, term: str) -> bool:
    normalized_term = _normalize_text(term)
    if not normalized_term:
        return False

    if re.fullmatch(r"\W+", normalized_term):
        return normalized_term in text

    if " " in normalized_term:
        return normalized_term in text

    return re.search(rf"(?<!\w){re.escape(normalized_term)}(?!\w)", text) is not None


def _matches_any_term(text: str, terms: list[str]) -> bool:
    return any(_contains_term(text, term) for term in terms)


def _count_matches(text: str, terms: list[str]) -> int:
    return sum(1 for term in terms if _contains_term(text, term))


def _video_text(video: dict) -> str:
    return _normalize_text(
        " ".join(
            [
                str(video.get("title", "")),
                str(video.get("channel_title", "")),
                str(video.get("keyword", "")),
            ]
        )
    )


def is_probably_spanish(video: dict) -> bool:
    raw_text = _video_text(video)
    return _matches_any_term(raw_text, SPANISH_STRONG_TERMS)


def is_probably_english(video: dict) -> bool:
    if video.get("niche") == "IA e tecnologia":
        return False

    raw_text = _video_text(video)
    return _matches_any_term(raw_text, ENGLISH_STRONG_TERMS)


def _is_valid_video(video: dict) -> bool:
    try:
        views = int(video.get("views", 0))
        published_at = _parse_datetime(video["published_at"])
    except (TypeError, ValueError, KeyError):
        return False

    if views < MIN_VIEWS:
        return False

    age_days = max(
        (datetime.now(timezone.utc) - published_at).total_seconds() / 86400, 0.1
    )
    views_per_day = views / age_days
    if views_per_day < MIN_VIEWS_PER_DAY:
        return False

    config = get_viral_config()
    if config["viral_only"] and config["viral_strict_mode"]:
        if not is_accepted_by_viral_mode(views, views_per_day, config):
            return False

    duration = int(video.get("duration_seconds", 0))
    if duration <= 0 or duration > 180:
        return False

    raw_text = _video_text(video)

    if is_probably_spanish(video):
        return False

    if is_probably_english(video):
        return False

    if _matches_any_term(raw_text, BLOCKED_WORDS):
        return False

    niche = video.get("niche", "")
    niche_words = NICHE_WORDS.get(niche, [])
    if not niche_words:
        return False

    return _matches_any_term(raw_text, niche_words)


def calculate_scores(video: dict) -> dict | None:
    now = datetime.now(timezone.utc)

    published_at = _parse_datetime(video["published_at"])
    age_days = max((now - published_at).total_seconds() / 86400, 0.1)

    views = int(video.get("views", 0))
    comments = int(video.get("comments", 0))
    duration = int(video.get("duration_seconds", 0))
    raw_text = _normalize_text(
        " ".join(
            [
                str(video.get("title", "")),
                str(video.get("channel_title", "")),
                str(video.get("keyword", "")),
                str(video.get("niche", "")),
            ]
        )
    )

    niche = video.get("niche", "")
    niche_words = NICHE_WORDS.get(niche, [])
    niche_matches = _count_matches(raw_text, niche_words)
    niche_relevance_score = min(niche_matches * 5, 15)

    views_per_day = views / age_days
    config = get_viral_config()
    viral_tier = classify_viral_tier(views, views_per_day, config)
    is_viral_candidate = is_candidate_by_viral_tier(viral_tier, config)

    if config["viral_only"] and not is_accepted_by_viral_mode(views, views_per_day, config):
        return None

    comment_rate = comments / views if views >= 50000 and views > 0 else 0

    matched_words = [
        word for word in DARK_FRIENDLY_WORDS if _contains_term(raw_text, word)
    ]
    dark_friendly_score = min(len(matched_words) * 2, 8)

    views_score = min(math.log10(views_per_day + 1) / math.log10(250000 + 1), 1) * 50

    if views >= 50000:
        comment_score = min(comment_rate / 0.02, 1) * 15
    else:
        comment_score = 0

    if age_days <= 2:
        freshness_score = 15
    elif age_days <= 7:
        freshness_score = 10
    elif age_days <= 14:
        freshness_score = 6
    else:
        freshness_score = 3

    if 30 <= duration <= 90:
        duration_score = 15
    elif 15 <= duration <= 120:
        duration_score = 10
    else:
        duration_score = 5

    opportunity_score = (
        views_score
        + comment_score
        + freshness_score
        + duration_score
        + dark_friendly_score
        + niche_relevance_score
    )

    score_cap = 100
    if 5000 <= views_per_day < 10000:
        score_cap = 82
    elif 10000 <= views_per_day < 25000:
        score_cap = 90

    opportunity_score = min(opportunity_score, score_cap)

    video["views_per_day"] = round(views_per_day, 2)
    video["comment_rate"] = round(comment_rate, 4)
    video["dark_friendly_score"] = round(dark_friendly_score, 2)
    video["niche_relevance_score"] = round(niche_relevance_score, 2)
    video["opportunity_score"] = round(min(opportunity_score, 100), 2)
    video["viral_tier"] = viral_tier
    video["is_viral_candidate"] = int(is_viral_candidate)

    if (
        viral_tier != "mega_viral"
        and config["min_opportunity_score"]
        and video["opportunity_score"] < config["min_opportunity_score"]
    ):
        return None

    return video


def score_videos(videos: list[dict]) -> list[dict]:
    scored = []

    for video in videos:
        if not _is_valid_video(video):
            continue

        scored_video = calculate_scores(video)
        if scored_video is None:
            continue

        scored.append(scored_video)

    return scored
