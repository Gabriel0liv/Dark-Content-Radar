import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from src.ai.constants import ANALYSIS_SCHEMA_VERSION
from src.ai.factory import get_ai_provider
from src.ai.json_utils import parse_tags
from src.pre_ai_filter import local_pre_ai_filter
from src.scorer import get_viral_config
from src.storage import (
    fetch_videos_for_ai_analysis,
    init_ai_analysis_table,
    init_db,
    save_ai_analysis,
)

VALID_CONTENT_PROFILES = {
    "general",
    "curiosity_ai_trends",
    "finance",
    "history_mystery",
    "psychology_behavior",
}
CURIOSITY_SAFE_CATEGORIES = {
    "ai_tech",
    "science",
    "curiosity",
    "psychology",
    "history",
    "mystery",
    "controversy",
    "news",
}
DIY_MARKERS = {
    "diy",
    "home repair",
    "lifehack",
    "life hack",
    "repair",
    "fix",
    "conserto",
    "reparo",
    "casa",
    "doméstico",
    "domestico",
}


def get_content_profile() -> str:
    content_profile = os.getenv("CONTENT_PROFILE", "curiosity_ai_trends").strip().lower()
    if content_profile not in VALID_CONTENT_PROFILES:
        print(
            f"[WARN] CONTENT_PROFILE inválido: {content_profile}. Usando curiosity_ai_trends."
        )
        return "curiosity_ai_trends"
    return content_profile


def calculate_production_priority_score(video: dict, analysis: dict, content_profile: str = "curiosity_ai_trends") -> float:
    base_score = (
        float(video.get("opportunity_score", 0)) * 0.25
        + float(analysis.get("creator_fit_score", 0)) * 0.25
        + float(analysis.get("localization_potential", 0)) * 0.20
        + float(analysis.get("cultural_fit_br", 0)) * 0.15
        + float(analysis.get("evergreen_score", 50)) * 0.10
        + float(analysis.get("dark_channel_fit", 0)) * 0.05
    )

    risk_penalty = (
        {"low": 0, "medium": 10, "high": 25}.get(
            analysis.get("copyright_risk"), 10
        )
        + {"low": 0, "medium": 10, "high": 25}.get(
            analysis.get("reused_content_risk"), 10
        )
        + {"low": 0, "medium": 15, "high": 35}.get(
            analysis.get("ip_risk"), 15
        )
        + {"low": 0, "medium": 8, "high": 20}.get(
            analysis.get("source_dependency_risk"), 8
        )
        + {"low": 0, "medium": 10, "high": 25}.get(
            analysis.get("brand_or_product_risk"), 10
        )
    )
    difficulty_penalty = {
        "low": 0,
        "medium": 8,
        "high": 18,
    }.get(analysis.get("production_difficulty"), 8)

    bonus = 0
    source_language = analysis.get("source_language")
    localization_potential = float(analysis.get("localization_potential", 0))
    adaptation_type = analysis.get("adaptation_type")
    recommended_action = analysis.get("recommended_action", "")

    if source_language == "pt":
        bonus += 5
    if source_language in {"en", "es"} and localization_potential >= 75:
        bonus += 8
    if adaptation_type == "foreign_adaptable":
        bonus += 8
    if adaptation_type == "global_trend":
        bonus += 8
    if recommended_action == "use_as_reference":
        bonus += 8
    if recommended_action == "adapt_with_research":
        bonus += 4

    score = base_score + bonus - risk_penalty - difficulty_penalty

    if content_profile == "curiosity_ai_trends":
        content_category = analysis.get("content_category")
        content_format = analysis.get("content_format")
        video_text = " ".join(
            [
                str(video.get("title", "")),
                str(video.get("description", "")),
                " ".join(parse_tags(video.get("tags"))),
            ]
        ).lower()
        has_generic_diy = any(marker in video_text for marker in DIY_MARKERS)

        if content_category in {"finance", "product"}:
            if (
                analysis.get("adaptation_type") not in {"global_trend", "foreign_adaptable"}
                and analysis.get("creator_fit_score", 0) < 75
                and analysis.get("localization_potential", 0) < 75
            ):
                score -= 12
        if analysis.get("adaptation_type") in {"source_too_contextual", "promotional", "reject"}:
            score -= 12
        if content_category in {"finance", "product"} and recommended_action != "adapt_with_research":
            score = min(score, 55)
        if content_category == "product":
            score = min(score, 45)
        if content_format == "tutorial" and content_category not in CURIOSITY_SAFE_CATEGORIES:
            score = min(score, 55)
        if has_generic_diy and content_category not in {"ai_tech", "science"}:
            score = min(score, 50)
        if analysis.get("brand_or_product_risk") != "low":
            score = min(score, 55)

    if recommended_action.startswith("reject_"):
        score = min(score, 25)
    if adaptation_type == "high_ip_risk":
        score = min(score, 20)
    if analysis.get("ip_risk") == "high":
        score = min(score, 20)
    if analysis.get("reused_content_risk") == "high":
        score = min(score, 25)
    if analysis.get("brand_or_product_risk") == "high":
        score = min(score, 30)
    if source_language != "pt" and localization_potential < 50:
        score = min(score, 40)
    if not analysis.get("is_good_reference", False):
        score = min(score, 40)
    if recommended_action == "needs_manual_review":
        score = min(score, 65)

    return round(max(0, min(100, score)), 2)


def _save_analysis_record(db_path: str, video: dict, analysis: dict, model_name: str) -> float:
    production_priority_score = calculate_production_priority_score(
        video=video,
        analysis=analysis,
        content_profile=str(video.get("content_profile", "curiosity_ai_trends")),
    )
    record = {
        "video_id": video["video_id"],
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "model": model_name,
        "is_good_reference": analysis["is_good_reference"],
        "detected_language": analysis["detected_language"],
        "source_language": analysis["source_language"],
        "target_market": analysis["target_market"],
        "real_niche": analysis["real_niche"],
        "content_category": analysis["content_category"],
        "content_type": analysis["content_type"],
        "content_format": analysis["content_format"],
        "adaptation_type": analysis["adaptation_type"],
        "hook_type": analysis["hook_type"],
        "retention_pattern": analysis["retention_pattern"],
        "dark_channel_fit": analysis["dark_channel_fit"],
        "creator_fit_score": analysis["creator_fit_score"],
        "localization_potential": analysis["localization_potential"],
        "cultural_fit_br": analysis["cultural_fit_br"],
        "evergreen_score": analysis["evergreen_score"],
        "production_difficulty": analysis["production_difficulty"],
        "originality_requirement": analysis["originality_requirement"],
        "copyright_risk": analysis["copyright_risk"],
        "reused_content_risk": analysis["reused_content_risk"],
        "source_dependency_risk": analysis["source_dependency_risk"],
        "ip_risk": analysis["ip_risk"],
        "brand_or_product_risk": analysis["brand_or_product_risk"],
        "controversy_level": analysis["controversy_level"],
        "fact_check_needed": analysis["fact_check_needed"],
        "recommended_action": analysis["recommended_action"],
        "opportunity_reason": analysis["opportunity_reason"],
        "original_angle_ideas": json.dumps(
            analysis["original_angle_ideas"], ensure_ascii=False
        ),
        "production_priority_score": production_priority_score,
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
        "raw_json": analysis.get(
            "raw_json", json.dumps(analysis, ensure_ascii=False)
        ),
    }
    save_ai_analysis(db_path, record)
    return production_priority_score


def _print_analysis_result(video: dict, analysis: dict, *, source: str, production_priority_score: float) -> None:
    print(f"[OK] {video['title']}")
    print(f"source: {source}")
    print(f"content_profile: {video.get('content_profile', 'curiosity_ai_trends')}")
    print(f"viral_tier: {video.get('viral_tier', 'unknown')}")
    print(f"views: {int(video.get('views', 0))}")
    print(f"views_per_day: {int(video.get('views_per_day', 0))}")
    print(
        f"good_reference: {'sim' if analysis['is_good_reference'] else 'não'}"
    )
    print(f"source_language: {analysis['source_language']}")
    print(f"creator_fit_score: {analysis['creator_fit_score']}")
    print(f"localization_potential: {analysis['localization_potential']}")
    print(f"production_priority_score: {production_priority_score}")
    print(f"recommended_action: {analysis['recommended_action']}")
    print(f"reason: {analysis['opportunity_reason']}")
    print()


def main() -> None:
    load_dotenv()

    db_path = os.getenv("DATABASE_PATH", "data/database.sqlite")
    analysis_limit = int(os.getenv("AI_ANALYSIS_LIMIT", "20"))
    batch_size = max(1, int(os.getenv("AI_ANALYSIS_BATCH_SIZE", "5")))
    content_profile = get_content_profile()
    viral_config = get_viral_config()
    provider = get_ai_provider()

    init_db(db_path)
    init_ai_analysis_table(db_path)

    videos = fetch_videos_for_ai_analysis(
        db_path,
        limit=analysis_limit,
        viral_only=viral_config["viral_only"],
    )
    if not videos:
        print("Nenhum vídeo novo encontrado para análise IA.")
        return

    for video in videos:
        video["content_profile"] = content_profile

    provider_model = f"{provider.provider_name}:{provider.model_name}"

    for start in range(0, len(videos), batch_size):
        batch = videos[start : start + batch_size]
        local_results: list[tuple[dict, dict]] = []
        provider_batch: list[dict] = []

        for video in batch:
            filtered = local_pre_ai_filter(video)
            if filtered is None:
                provider_batch.append(video)
            else:
                local_results.append((video, filtered))

        for video, analysis in local_results:
            production_priority_score = _save_analysis_record(
                db_path=db_path,
                video=video,
                analysis=analysis,
                model_name="local-filter",
            )
            _print_analysis_result(
                video,
                analysis,
                source="local-filter",
                production_priority_score=production_priority_score,
            )

        if not provider_batch:
            continue

        try:
            analyses = provider.analyze_video_opportunities_batch(provider_batch)
        except Exception as error:
            print(f"[ERRO] Falha no batch {start // batch_size + 1}: {error}")
            print(
                "[INFO] Tentando processar os vídeos individualmente para preservar o progresso."
            )
            analyses = []
            for video in provider_batch:
                try:
                    analyses.append(provider.analyze_video_opportunity(video))
                except Exception as item_error:
                    print(f"[ERRO] {video['title']}")
                    print(f"reason: {item_error}")
                    print()
            if not analyses:
                continue

        analyses_by_id = {
            str(analysis.get("video_id", "")).strip(): analysis for analysis in analyses
        }

        for video in provider_batch:
            analysis = analyses_by_id.get(str(video["video_id"]).strip())
            if not analysis:
                continue

            production_priority_score = _save_analysis_record(
                db_path=db_path,
                video=video,
                analysis=analysis,
                model_name=provider_model,
            )
            _print_analysis_result(
                video,
                analysis,
                source=provider_model,
                production_priority_score=production_priority_score,
            )


if __name__ == "__main__":
    main()
