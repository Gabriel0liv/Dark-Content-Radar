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


def format_number(value) -> str:
    number = float(value or 0)
    if number >= 1_000_000:
        formatted = number / 1_000_000
        return f"{formatted:.1f}M".replace(".0M", "M")
    if number >= 1_000:
        formatted = number / 1_000
        return f"{formatted:.1f}K".replace(".0K", "K")
    return str(int(number))


def main():
    load_dotenv()

    api_key = os.getenv("YOUTUBE_API_KEY")
    db_path = os.getenv("DATABASE_PATH", "data/database.sqlite")
    days_back = int(os.getenv("DAYS_BACK", "7"))
    region_code = os.getenv("REGION_CODE", "BR")
    max_results = int(os.getenv("MAX_RESULTS_PER_KEYWORD", "50"))
    max_pages = int(os.getenv("MAX_SEARCH_PAGES_PER_KEYWORD", "2"))

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
                    max_results=max_results,
                    max_pages=max_pages,
                )

                scored = score_videos(videos)
                all_videos.extend(scored)
                tier_counts = {
                    "mega_viral": sum(1 for video in scored if video.get("viral_tier") == "mega_viral"),
                    "viral": sum(1 for video in scored if video.get("viral_tier") == "viral"),
                    "rising": sum(1 for video in scored if video.get("viral_tier") == "rising"),
                }

                print(
                    f"Coletados: {len(videos)} | Aprovados: {len(scored)} | "
                    f"mega: {tier_counts['mega_viral']} | viral: {tier_counts['viral']} | rising: {tier_counts['rising']}"
                )

            except Exception as error:
                print(f"Erro ao buscar '{keyword}': {error}")

    if all_videos:
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
        print(
            f"{index}. [{video['niche']}] "
            f"{video['opportunity_score']} pts | "
            f"{format_number(video.get('views', 0))} views | "
            f"{format_number(video.get('views_per_day', 0))} views/dia | "
            f"{video.get('viral_tier', 'weak')} | "
            f"{video['title']} | "
            f"{video['url']}"
        )

    print(
        "\nEste ranking mostra apenas sinais brutos do YouTube que passaram nos filtros de viralidade configurados no .env. "
        "Para ver oportunidades reais de produção, rode python analyze.py e abra o painel com streamlit run app.py."
    )


if __name__ == "__main__":
    main()
