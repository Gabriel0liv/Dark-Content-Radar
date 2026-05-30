import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from src.scorer import get_viral_config, score_videos
from src.storage import (
    fetch_top_videos_balanced,
    init_ai_analysis_table,
    init_db,
    upsert_videos,
)
from src.youtube_collector import search_recent_short_videos
from src.youtube_collector import fetch_popular_short_videos

KEYWORDS_BY_NICHE = {
    "História sombria": [
        "história sombria",
        "curiosidades históricas",
        "fatos históricos",
        "mistérios da história",
        "história bizarra",
    ],
    "Psicologia": [
        "fatos psicológicos",
        "psicologia humana",
        "comportamento humano",
        "curiosidades sobre o cérebro",
        "mente humana",
    ],
    "Mistérios reais": [
        "mistérios reais",
        "casos inexplicáveis",
        "fatos bizarros",
        "histórias reais assustadoras",
        "casos estranhos reais",
    ],
    "IA e tecnologia": [
        "ferramentas de ia",
        "inteligência artificial",
        "chatgpt produtividade",
        "apps de ia",
        "automação com ia",
    ],
    "Finanças básicas": [
        "erros financeiros",
        "finanças pessoais",
        "economizar dinheiro",
        "hábitos financeiros",
        "educação financeira",
    ],
}

BROAD_VIRAL_QUERIES_BY_NICHE = {
    "Geral viral": [
        "curiosidades",
        "fatos interessantes",
        "você sabia",
        "coisas que você não sabia",
        "história real",
        "fato bizarro",
        "isso aconteceu",
        "viral shorts",
        "curiosities",
        "did you know",
        "crazy facts",
        "weird facts",
        "strange facts",
        "interesting facts",
        "science facts",
        "history facts",
        "AI news",
        "AI tools",
        "psychology facts",
    ],
    "IA e tecnologia": [
        "AI",
        "artificial intelligence",
        "AI tools",
        "new AI",
        "ChatGPT",
        "Claude AI",
        "Gemini AI",
        "AI automation",
        "tecnologia",
        "inteligência artificial",
        "ferramentas de IA",
    ],
    "Curiosidades e ciência": [
        "science facts",
        "weird science",
        "curiosidades científicas",
        "fatos científicos",
        "experimento científico",
        "brain facts",
        "cérebro",
    ],
    "História e mistério": [
        "history facts",
        "weird history",
        "dark history",
        "ancient history",
        "mystery facts",
        "curiosidades históricas",
        "história bizarra",
        "mistérios",
    ],
}


def format_number(value) -> str:
    number = float(value or 0)
    if number >= 1_000_000:
        formatted = number / 1_000_000
        return f"{formatted:.1f}M".replace(".0M", "M")
    if number >= 1_000:
        formatted = number / 1_000
        return f"{formatted:.1f}K".replace(".0K", "K")
    return str(int(number))


def parse_csv(value: str, default: list[str]) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or default


def enabled_discovery_sources(discovery_mode: str) -> set[str]:
    discovery_mode = discovery_mode.strip().lower()
    if discovery_mode == "hybrid":
        return {"niche_keywords", "broad_viral", "youtube_popular"}
    if discovery_mode in {"niche_keywords", "broad_viral", "youtube_popular"}:
        return {discovery_mode}
    print(f"[WARN] DISCOVERY_MODE inválido: {discovery_mode}. Usando hybrid.")
    return {"niche_keywords", "broad_viral", "youtube_popular"}


def tier_counts(videos: list[dict]) -> dict[str, int]:
    return {
        "mega_viral": sum(1 for video in videos if video.get("viral_tier") == "mega_viral"),
        "viral": sum(1 for video in videos if video.get("viral_tier") == "viral"),
        "rising": sum(1 for video in videos if video.get("viral_tier") == "rising"),
    }


def log_collection(source: str, candidate_niche: str, query: str, collected: int, scored: list[dict]) -> None:
    counts = tier_counts(scored)
    print(
        f"Fonte: {source} | Nicho candidato: {candidate_niche} | Query: {query}"
    )
    print(
        f"Coletados: {collected} | Aprovados: {len(scored)} | "
        f"mega: {counts['mega_viral']} | viral: {counts['viral']} | rising: {counts['rising']}"
    )


def dedupe_videos(videos: list[dict]) -> list[dict]:
    deduped: dict[str, dict] = {}
    for video in videos:
        video_id = video.get("video_id")
        if not video_id:
            continue
        existing = deduped.get(video_id)
        if existing is None or float(video.get("opportunity_score", 0)) > float(existing.get("opportunity_score", 0)):
            deduped[video_id] = video
    return list(deduped.values())


def main():
    load_dotenv()

    api_key = os.getenv("YOUTUBE_API_KEY")
    db_path = os.getenv("DATABASE_PATH", "data/database.sqlite")
    days_back = int(os.getenv("DISCOVERY_DAYS_BACK", os.getenv("DAYS_BACK", "30")))
    region_code = os.getenv("REGION_CODE", "BR")
    max_results = int(os.getenv("MAX_RESULTS_PER_KEYWORD", "50"))
    max_pages = int(os.getenv("MAX_SEARCH_PAGES_PER_KEYWORD", "2"))
    discovery_sources = enabled_discovery_sources(os.getenv("DISCOVERY_MODE", "hybrid"))
    discovery_regions = parse_csv(os.getenv("DISCOVERY_REGIONS", "BR,US"), ["BR", "US"])
    discovery_languages = parse_csv(os.getenv("DISCOVERY_LANGUAGES", "pt,en,es"), ["pt", "en", "es"])
    popular_regions = parse_csv(os.getenv("YOUTUBE_POPULAR_REGIONS", "BR,US"), ["BR", "US"])
    popular_categories = parse_csv(os.getenv("YOUTUBE_POPULAR_CATEGORIES", "28,27,24,22"), ["28", "27", "24", "22"])

    if not api_key:
        raise RuntimeError("Falta YOUTUBE_API_KEY no arquivo .env")

    viral_config = get_viral_config()
    print("CONFIGURAÇÃO DE VIRALIDADE")
    print("==========================")
    print(f"VIRAL_ONLY={str(viral_config['viral_only']).lower()}")
    print(f"VIRAL_ACCEPTANCE_MODE={viral_config['viral_acceptance_mode']}")
    print(f"MIN_TOTAL_VIEWS={viral_config['min_total_views']}")
    print(f"MIN_VIEWS_PER_DAY={viral_config['min_views_per_day']}")
    print(f"MIN_RISING_TOTAL_VIEWS={viral_config['min_rising_total_views']}")
    print(f"MIN_RISING_VIEWS_PER_DAY={viral_config['min_rising_views_per_day']}")
    print(f"MIN_OPPORTUNITY_SCORE={viral_config['min_opportunity_score']}")
    print(f"VIRAL_STRICT_MODE={str(viral_config['viral_strict_mode']).lower()}")
    print(f"MAX_SEARCH_PAGES_PER_KEYWORD={max_pages}")
    print(f"MAX_RESULTS_PER_KEYWORD={max_results}")
    print()

    init_db(db_path)
    init_ai_analysis_table(db_path)

    published_after = datetime.now(timezone.utc) - timedelta(days=days_back)

    all_videos = []

    if "niche_keywords" in discovery_sources:
        print("\n=== Discovery: niche_keywords ===")
        for niche, keywords in KEYWORDS_BY_NICHE.items():
            print(f"\n=== Nicho: {niche} ===")

            for keyword in keywords:
                print(f"Buscando: {keyword}")

                try:
                    videos = search_recent_short_videos(
                        api_key=api_key,
                        keyword=keyword,
                        niche=niche,
                        published_after=published_after,
                        region_code=region_code,
                        relevance_language="pt",
                        max_results=max_results,
                        max_pages=max_pages,
                        discovery_source="niche_keywords",
                        discovery_query=keyword,
                        candidate_niche=niche,
                    )

                    scored = score_videos(videos)
                    all_videos.extend(scored)
                    log_collection("niche_keywords", niche, keyword, len(videos), scored)

                except Exception as error:
                    print(f"Erro ao buscar '{keyword}': {error}")

    if "broad_viral" in discovery_sources:
        print("\n=== Discovery: broad_viral ===")
        for candidate_niche, queries in BROAD_VIRAL_QUERIES_BY_NICHE.items():
            for query in queries:
                for discovery_region in discovery_regions:
                    for discovery_language in discovery_languages:
                        try:
                            videos = search_recent_short_videos(
                                api_key=api_key,
                                keyword=query,
                                niche=candidate_niche,
                                published_after=published_after,
                                region_code=discovery_region,
                                relevance_language=discovery_language,
                                max_results=max_results,
                                max_pages=max_pages,
                                discovery_source="broad_viral",
                                discovery_query=f"{query}:{discovery_region}:{discovery_language}",
                                candidate_niche=candidate_niche,
                            )
                            scored = score_videos(videos)
                            all_videos.extend(scored)
                            log_collection(
                                "broad_viral",
                                candidate_niche,
                                f"{query}:{discovery_region}:{discovery_language}",
                                len(videos),
                                scored,
                            )
                        except Exception as error:
                            print(f"Erro ao buscar '{query}' em {discovery_region}/{discovery_language}: {error}")

    if "youtube_popular" in discovery_sources:
        print("\n=== Discovery: youtube_popular ===")
        for popular_region in popular_regions:
            for category_id in popular_categories:
                try:
                    videos = fetch_popular_short_videos(
                        api_key=api_key,
                        region_code=popular_region,
                        video_category_id=category_id,
                        max_results=max_results,
                        pages=max_pages,
                    )
                    scored = score_videos(videos)
                    all_videos.extend(scored)
                    log_collection(
                        "youtube_popular",
                        "YouTube popular",
                        f"mostPopular:{popular_region}:{category_id}",
                        len(videos),
                        scored,
                    )
                except Exception as error:
                    print(f"Erro ao buscar mostPopular {popular_region}/{category_id}: {error}")

    if all_videos:
        all_videos = dedupe_videos(all_videos)
        collected_at = datetime.now(timezone.utc).isoformat()

        for video in all_videos:
            video["collected_at"] = collected_at

        upsert_videos(db_path, all_videos)

    print("\n\nTOP SINAIS VIRAIS DO YOUTUBE — RANKING BALANCEADO")
    print("=================================================")

    top_videos = fetch_top_videos_balanced(db_path, per_niche=20, total_limit=200)
    if viral_config["viral_only"]:
        top_videos = [
            video for video in top_videos if video.get("is_viral_candidate")
        ]
    top_videos = top_videos[:20]

    for index, video in enumerate(top_videos, start=1):
        display_niche = video.get("real_niche") or video.get("candidate_niche") or video.get("niche")
        print(
            f"{index}. [{display_niche}] "
            f"{video['opportunity_score']} pts | "
            f"{format_number(video.get('views', 0))} views | "
            f"{format_number(video.get('views_per_day', 0))} views/dia | "
            f"{video.get('viral_tier', 'weak')} | "
            f"{video.get('discovery_source', 'niche_keywords')} | "
            f"{video['title']} | "
            f"{video['url']}"
        )

    print(
        "\nEste ranking mostra apenas sinais brutos do YouTube que passaram nos filtros de viralidade configurados no .env. "
        "Para ver oportunidades reais de produção, rode python analyze.py e abra o painel com streamlit run app.py."
    )


if __name__ == "__main__":
    main()
