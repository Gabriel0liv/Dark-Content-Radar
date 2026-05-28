import os
import json

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.storage import (
    fetch_top_videos,
    fetch_top_videos_balanced,
    init_ai_analysis_table,
    init_db,
)

load_dotenv()

DB_PATH = os.getenv("DATABASE_PATH", "data/database.sqlite")

st.set_page_config(
    page_title="Dark Content Radar",
    page_icon="📊",
    layout="wide",
)

st.title("Dark Content Radar")
st.caption("Portal de inteligência de conteúdo para encontrar oportunidades originais a partir do YouTube Shorts.")

init_db(DB_PATH)
init_ai_analysis_table(DB_PATH)

with st.sidebar:
    st.header("Filtros")

    ranking_mode = st.selectbox(
        "Modo de ranking",
        options=["Geral", "Balanceado por nicho"],
        index=0,
    )

if ranking_mode == "Balanceado por nicho":
    videos = fetch_top_videos_balanced(DB_PATH, per_niche=5, total_limit=500)
else:
    videos = fetch_top_videos(DB_PATH, limit=500)

if not videos:
    st.warning("Ainda não existem vídeos no banco. Rode primeiro: python main.py")
    st.stop()

df = pd.DataFrame(videos)
has_niche_relevance_score = "niche_relevance_score" in df.columns

with st.sidebar:
    niches = sorted(df["niche"].dropna().unique().tolist())
    selected_niches = st.multiselect(
        "Nichos",
        options=niches,
        default=niches,
    )

    min_score = st.slider(
        "Score mínimo",
        min_value=0,
        max_value=100,
        value=40,
    )

    min_views_per_day = st.number_input(
        "Views/dia mínimo",
        min_value=0,
        value=0,
        step=1000,
    )

    source_language_filter = st.selectbox(
        "Source language",
        options=["all", "pt", "en", "es", "unknown"],
        index=0,
    )

    recommended_action_options = (
        ["all"]
        + sorted(
            [
                value
                for value in df.get("recommended_action", pd.Series(dtype=str)).dropna().unique().tolist()
            ]
        )
    )
    recommended_action_filter = st.selectbox(
        "Recommended action",
        options=recommended_action_options,
        index=0,
    )

    content_category_options = (
        ["all"]
        + sorted(
            [
                value
                for value in df.get("content_category", pd.Series(dtype=str)).dropna().unique().tolist()
            ]
        )
    )
    content_category_filter = st.selectbox(
        "Content category",
        options=content_category_options,
        index=0,
    )

    adaptation_type_options = (
        ["all"]
        + sorted(
            [
                value
                for value in df.get("adaptation_type", pd.Series(dtype=str)).dropna().unique().tolist()
            ]
        )
    )
    adaptation_type_filter = st.selectbox(
        "Adaptation type",
        options=adaptation_type_options,
        index=0,
    )

    min_localization_potential = st.slider(
        "Localization potential mínimo",
        min_value=0,
        max_value=100,
        value=0,
    )

    min_creator_fit = st.slider(
        "Creator fit mínimo",
        min_value=0,
        max_value=100,
        value=0,
    )

    max_ip_risk = st.selectbox(
        "IP risk máximo",
        options=["high", "medium", "low"],
        index=0,
    )

    only_good_references = st.checkbox(
        "Mostrar apenas boas referências",
        value=False,
    )
    only_foreign_adaptable = st.checkbox(
        "Mostrar apenas oportunidades adaptáveis da gringa",
        value=False,
    )
    st.caption("Esse filtro só funciona depois de rodar `python analyze.py`.")

filtered = df[
    (df["niche"].isin(selected_niches))
    & (df["opportunity_score"] >= min_score)
    & (df["views_per_day"] >= min_views_per_day)
].copy()

risk_order = {"low": 1, "medium": 2, "high": 3}

if "source_language" in filtered.columns and source_language_filter != "all":
    filtered = filtered[filtered["source_language"] == source_language_filter].copy()

if "recommended_action" in filtered.columns and recommended_action_filter != "all":
    filtered = filtered[filtered["recommended_action"] == recommended_action_filter].copy()

if "content_category" in filtered.columns and content_category_filter != "all":
    filtered = filtered[filtered["content_category"] == content_category_filter].copy()

if "adaptation_type" in filtered.columns and adaptation_type_filter != "all":
    filtered = filtered[filtered["adaptation_type"] == adaptation_type_filter].copy()

if "localization_potential" in filtered.columns:
    filtered = filtered[filtered["localization_potential"].fillna(0) >= min_localization_potential].copy()

if "creator_fit_score" in filtered.columns:
    filtered = filtered[filtered["creator_fit_score"].fillna(0) >= min_creator_fit].copy()

if "ip_risk" in filtered.columns:
    filtered = filtered[
        filtered["ip_risk"].fillna("high").map(risk_order).fillna(3) <= risk_order[max_ip_risk]
    ].copy()

has_ai_analyses = (
    "is_good_reference" in df.columns
    and df["is_good_reference"].notna().sum() > 0
)

if only_good_references:
    if has_ai_analyses:
        filtered = filtered[filtered["is_good_reference"] == 1].copy()

if only_foreign_adaptable and has_ai_analyses:
    filtered = filtered[
        filtered["source_language"].isin(["en", "es"])
        & filtered["recommended_action"].isin(["use_as_reference", "adapt_with_research"])
        & (filtered["localization_potential"].fillna(0) >= 70)
    ].copy()


def _format_ideas(value):
    if not value:
        return ""

    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return str(value)

    if not isinstance(parsed, list):
        return str(value)

    return " | ".join(str(item) for item in parsed if str(item).strip())


if "original_angle_ideas" in filtered.columns:
    filtered["original_angle_ideas"] = filtered["original_angle_ideas"].apply(
        _format_ideas
    )

col1, col2, col3, col4 = st.columns(4)

col1.metric("Vídeos no banco", len(df))
col2.metric("Vídeos filtrados", len(filtered))
col3.metric(
    "Maior score",
    round(filtered["opportunity_score"].max(), 2) if not filtered.empty else 0,
)
col4.metric(
    "Maior views/dia", int(filtered["views_per_day"].max()) if not filtered.empty else 0
)

st.subheader("Top oportunidades")

show_columns = [
    "opportunity_score",
    "niche",
    "title",
    "channel_title",
    "views",
    "views_per_day",
    "comments",
    "comment_rate",
    "duration_seconds",
    "url",
]

if has_niche_relevance_score:
    show_columns.insert(2, "niche_relevance_score")

st.dataframe(
    filtered[show_columns].sort_values(
        by=["opportunity_score", "views_per_day"],
        ascending=False,
    ),
    use_container_width=True,
    hide_index=True,
)

st.subheader("Análise IA")

ai_columns = [
    "source_language",
    "target_market",
    "content_category",
    "content_format",
    "adaptation_type",
    "is_good_reference",
    "detected_language",
    "real_niche",
    "hook_type",
    "dark_channel_fit",
    "creator_fit_score",
    "localization_potential",
    "cultural_fit_br",
    "evergreen_score",
    "production_priority_score",
    "production_difficulty",
    "copyright_risk",
    "reused_content_risk",
    "ip_risk",
    "source_dependency_risk",
    "brand_or_product_risk",
    "controversy_level",
    "recommended_action",
    "opportunity_reason",
    "original_angle_ideas",
]

available_ai_columns = [column for column in ai_columns if column in filtered.columns]

if only_good_references and not has_ai_analyses:
    st.warning(
        "O filtro 'Mostrar apenas boas referências' exige análises IA salvas. Rode `python analyze.py` primeiro."
    )
elif not has_ai_analyses:
    st.info("Ainda não existem análises IA salvas. Rode: python analyze.py")
else:
    ai_df = filtered[
        [
            "title",
            "channel_title",
            "niche",
            "opportunity_score",
            "url",
            *available_ai_columns,
        ]
    ].copy()
    st.dataframe(
        ai_df.sort_values(
            by=[
                "production_priority_score",
                "localization_potential",
                "creator_fit_score",
                "opportunity_score",
            ],
            ascending=[False, False, False, False],
        ),
        use_container_width=True,
        hide_index=True,
    )

st.subheader("Resumo por nicho")

if filtered.empty:
    summary = pd.DataFrame(
        columns=[
            "niche",
            "videos",
            "avg_score",
            "max_score",
            "avg_views_per_day",
            "max_views_per_day",
        ]
    )
else:
    summary = (
        filtered.groupby("niche")
        .agg(
            videos=("video_id", "count"),
            avg_score=("opportunity_score", "mean"),
            max_score=("opportunity_score", "max"),
            avg_views_per_day=("views_per_day", "mean"),
            max_views_per_day=("views_per_day", "max"),
        )
        .sort_values(by="max_score", ascending=False)
        .reset_index()
    )

st.dataframe(summary, use_container_width=True, hide_index=True)
