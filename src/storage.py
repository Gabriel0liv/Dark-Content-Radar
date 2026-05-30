import json
import sqlite3
from pathlib import Path
from typing import Iterable

from src.ai.constants import ANALYSIS_SCHEMA_VERSION


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    with get_connection(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                tags TEXT,
                category_id TEXT,
                default_language TEXT,
                default_audio_language TEXT,
                discovery_source TEXT,
                discovery_query TEXT,
                candidate_niche TEXT,
                channel_id TEXT,
                channel_title TEXT,
                published_at TEXT,
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                duration_seconds INTEGER DEFAULT 0,
                url TEXT,
                keyword TEXT,
                niche TEXT,
                views_per_day REAL DEFAULT 0,
                comment_rate REAL DEFAULT 0,
                dark_friendly_score REAL DEFAULT 0,
                niche_relevance_score REAL DEFAULT 0,
                opportunity_score REAL DEFAULT 0,
                viral_tier TEXT,
                is_viral_candidate INTEGER DEFAULT 0,
                collected_at TEXT
            )
            """)
        _ensure_column(conn, "videos", "niche_relevance_score", "REAL DEFAULT 0")
        _ensure_column(conn, "videos", "description", "TEXT")
        _ensure_column(conn, "videos", "tags", "TEXT")
        _ensure_column(conn, "videos", "category_id", "TEXT")
        _ensure_column(conn, "videos", "default_language", "TEXT")
        _ensure_column(conn, "videos", "default_audio_language", "TEXT")
        _ensure_column(conn, "videos", "discovery_source", "TEXT")
        _ensure_column(conn, "videos", "discovery_query", "TEXT")
        _ensure_column(conn, "videos", "candidate_niche", "TEXT")
        _ensure_column(conn, "videos", "viral_tier", "TEXT")
        _ensure_column(conn, "videos", "is_viral_candidate", "INTEGER DEFAULT 0")
        conn.commit()


def init_ai_analysis_table(db_path: str) -> None:
    with get_connection(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_video_analysis (
                video_id TEXT PRIMARY KEY,
                analyzed_at TEXT NOT NULL,
                model TEXT NOT NULL,
                is_good_reference INTEGER NOT NULL,
                detected_language TEXT,
                source_language TEXT,
                target_market TEXT,
                real_niche TEXT,
                content_category TEXT,
                content_type TEXT,
                content_format TEXT,
                adaptation_type TEXT,
                hook_type TEXT,
                retention_pattern TEXT,
                dark_channel_fit INTEGER,
                creator_fit_score INTEGER DEFAULT 0,
                localization_potential INTEGER DEFAULT 0,
                cultural_fit_br INTEGER DEFAULT 0,
                evergreen_score INTEGER DEFAULT 0,
                production_difficulty TEXT,
                originality_requirement TEXT,
                copyright_risk TEXT,
                reused_content_risk TEXT,
                source_dependency_risk TEXT,
                ip_risk TEXT,
                brand_or_product_risk TEXT,
                controversy_level TEXT,
                fact_check_needed INTEGER,
                recommended_action TEXT,
                opportunity_reason TEXT,
                original_angle_ideas TEXT,
                production_priority_score REAL DEFAULT 0,
                analysis_schema_version INTEGER DEFAULT 1,
                raw_json TEXT,
                FOREIGN KEY(video_id) REFERENCES videos(video_id)
            )
            """)
        _ensure_column(conn, "ai_video_analysis", "source_language", "TEXT")
        _ensure_column(conn, "ai_video_analysis", "target_market", "TEXT")
        _ensure_column(conn, "ai_video_analysis", "content_category", "TEXT")
        _ensure_column(conn, "ai_video_analysis", "content_format", "TEXT")
        _ensure_column(conn, "ai_video_analysis", "adaptation_type", "TEXT")
        _ensure_column(conn, "ai_video_analysis", "localization_potential", "INTEGER DEFAULT 0")
        _ensure_column(conn, "ai_video_analysis", "cultural_fit_br", "INTEGER DEFAULT 0")
        _ensure_column(conn, "ai_video_analysis", "creator_fit_score", "INTEGER DEFAULT 0")
        _ensure_column(conn, "ai_video_analysis", "evergreen_score", "INTEGER DEFAULT 0")
        _ensure_column(conn, "ai_video_analysis", "originality_requirement", "TEXT")
        _ensure_column(conn, "ai_video_analysis", "source_dependency_risk", "TEXT")
        _ensure_column(conn, "ai_video_analysis", "ip_risk", "TEXT")
        _ensure_column(conn, "ai_video_analysis", "brand_or_product_risk", "TEXT")
        _ensure_column(conn, "ai_video_analysis", "controversy_level", "TEXT")
        _ensure_column(conn, "ai_video_analysis", "recommended_action", "TEXT")
        _ensure_column(conn, "ai_video_analysis", "analysis_schema_version", "INTEGER DEFAULT 1")
        _ensure_column(
            conn,
            "ai_video_analysis",
            "production_priority_score",
            "REAL DEFAULT 0",
        )
        conn.commit()


def _ensure_column(
    conn: sqlite3.Connection, table_name: str, column_name: str, column_definition: str
) -> None:
    existing_columns = {
        row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }

    if column_name not in existing_columns:
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def _row_to_analysis_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None

    analysis = dict(row)
    analysis["is_good_reference"] = bool(analysis.get("is_good_reference", 0))
    analysis["fact_check_needed"] = bool(analysis.get("fact_check_needed", 0))
    return analysis


def _normalize_video_record(record: dict) -> dict:
    if record.get("is_good_reference") is not None:
        record["is_good_reference"] = bool(record["is_good_reference"])

    if record.get("fact_check_needed") is not None:
        record["fact_check_needed"] = bool(record["fact_check_needed"])

    if record.get("is_viral_candidate") is not None:
        record["is_viral_candidate"] = bool(record["is_viral_candidate"])

    return record


def upsert_videos(db_path: str, videos: Iterable[dict]) -> None:
    payloads = []
    for video in videos:
        payload = dict(video)
        tags = payload.get("tags")
        if isinstance(tags, list):
            payload["tags"] = json.dumps(tags, ensure_ascii=False)
        elif tags is None:
            payload["tags"] = json.dumps([], ensure_ascii=False)
        payload["is_viral_candidate"] = int(bool(payload.get("is_viral_candidate", 0)))
        payload.setdefault("discovery_source", "niche_keywords")
        payload.setdefault("discovery_query", payload.get("keyword", ""))
        payload.setdefault("candidate_niche", payload.get("niche", ""))
        payloads.append(payload)

    with get_connection(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO videos (
                video_id, title, description, tags, category_id, default_language,
                default_audio_language, discovery_source, discovery_query, candidate_niche,
                channel_id, channel_title, published_at,
                views, likes, comments, duration_seconds, url,
                keyword, niche, views_per_day, comment_rate,
                dark_friendly_score, niche_relevance_score, opportunity_score,
                viral_tier, is_viral_candidate, collected_at
            )
            VALUES (
                :video_id, :title, :description, :tags, :category_id, :default_language,
                :default_audio_language, :discovery_source, :discovery_query, :candidate_niche,
                :channel_id, :channel_title, :published_at,
                :views, :likes, :comments, :duration_seconds, :url,
                :keyword, :niche, :views_per_day, :comment_rate,
                :dark_friendly_score, :niche_relevance_score, :opportunity_score,
                :viral_tier, :is_viral_candidate, :collected_at
            )
            ON CONFLICT(video_id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                tags = excluded.tags,
                category_id = excluded.category_id,
                default_language = excluded.default_language,
                default_audio_language = excluded.default_audio_language,
                discovery_source = excluded.discovery_source,
                discovery_query = excluded.discovery_query,
                candidate_niche = excluded.candidate_niche,
                channel_id = excluded.channel_id,
                channel_title = excluded.channel_title,
                published_at = excluded.published_at,
                views = excluded.views,
                likes = excluded.likes,
                comments = excluded.comments,
                duration_seconds = excluded.duration_seconds,
                url = excluded.url,
                keyword = excluded.keyword,
                niche = excluded.niche,
                views_per_day = excluded.views_per_day,
                comment_rate = excluded.comment_rate,
                dark_friendly_score = excluded.dark_friendly_score,
                niche_relevance_score = excluded.niche_relevance_score,
                opportunity_score = excluded.opportunity_score,
                viral_tier = excluded.viral_tier,
                is_viral_candidate = excluded.is_viral_candidate,
                collected_at = excluded.collected_at
            """,
            payloads,
        )
        conn.commit()


def save_ai_analysis(db_path: str, analysis: dict) -> None:
    payload = dict(analysis)
    payload["is_good_reference"] = int(bool(payload.get("is_good_reference")))
    payload["fact_check_needed"] = int(bool(payload.get("fact_check_needed")))
    payload["analysis_schema_version"] = ANALYSIS_SCHEMA_VERSION

    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO ai_video_analysis (
                video_id,
                analyzed_at,
                model,
                is_good_reference,
                detected_language,
                source_language,
                target_market,
                real_niche,
                content_category,
                content_type,
                content_format,
                adaptation_type,
                hook_type,
                retention_pattern,
                dark_channel_fit,
                creator_fit_score,
                localization_potential,
                cultural_fit_br,
                evergreen_score,
                production_difficulty,
                originality_requirement,
                copyright_risk,
                reused_content_risk,
                source_dependency_risk,
                ip_risk,
                brand_or_product_risk,
                controversy_level,
                fact_check_needed,
                recommended_action,
                opportunity_reason,
                original_angle_ideas,
                production_priority_score,
                analysis_schema_version,
                raw_json
            )
            VALUES (
                :video_id,
                :analyzed_at,
                :model,
                :is_good_reference,
                :detected_language,
                :source_language,
                :target_market,
                :real_niche,
                :content_category,
                :content_type,
                :content_format,
                :adaptation_type,
                :hook_type,
                :retention_pattern,
                :dark_channel_fit,
                :creator_fit_score,
                :localization_potential,
                :cultural_fit_br,
                :evergreen_score,
                :production_difficulty,
                :originality_requirement,
                :copyright_risk,
                :reused_content_risk,
                :source_dependency_risk,
                :ip_risk,
                :brand_or_product_risk,
                :controversy_level,
                :fact_check_needed,
                :recommended_action,
                :opportunity_reason,
                :original_angle_ideas,
                :production_priority_score,
                :analysis_schema_version,
                :raw_json
            )
            ON CONFLICT(video_id) DO UPDATE SET
                analyzed_at = excluded.analyzed_at,
                model = excluded.model,
                is_good_reference = excluded.is_good_reference,
                detected_language = excluded.detected_language,
                source_language = excluded.source_language,
                target_market = excluded.target_market,
                real_niche = excluded.real_niche,
                content_category = excluded.content_category,
                content_type = excluded.content_type,
                content_format = excluded.content_format,
                adaptation_type = excluded.adaptation_type,
                hook_type = excluded.hook_type,
                retention_pattern = excluded.retention_pattern,
                dark_channel_fit = excluded.dark_channel_fit,
                creator_fit_score = excluded.creator_fit_score,
                localization_potential = excluded.localization_potential,
                cultural_fit_br = excluded.cultural_fit_br,
                evergreen_score = excluded.evergreen_score,
                production_difficulty = excluded.production_difficulty,
                originality_requirement = excluded.originality_requirement,
                copyright_risk = excluded.copyright_risk,
                reused_content_risk = excluded.reused_content_risk,
                source_dependency_risk = excluded.source_dependency_risk,
                ip_risk = excluded.ip_risk,
                brand_or_product_risk = excluded.brand_or_product_risk,
                controversy_level = excluded.controversy_level,
                fact_check_needed = excluded.fact_check_needed,
                recommended_action = excluded.recommended_action,
                opportunity_reason = excluded.opportunity_reason,
                original_angle_ideas = excluded.original_angle_ideas,
                production_priority_score = excluded.production_priority_score,
                analysis_schema_version = excluded.analysis_schema_version,
                raw_json = excluded.raw_json
            """,
            payload,
        )
        conn.commit()


def get_ai_analysis(db_path: str, video_id: str) -> dict | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                video_id,
                analyzed_at,
                model,
                is_good_reference,
                detected_language,
                source_language,
                target_market,
                real_niche,
                content_category,
                content_type,
                content_format,
                adaptation_type,
                hook_type,
                retention_pattern,
                dark_channel_fit,
                creator_fit_score,
                localization_potential,
                cultural_fit_br,
                evergreen_score,
                production_difficulty,
                originality_requirement,
                copyright_risk,
                reused_content_risk,
                source_dependency_risk,
                ip_risk,
                brand_or_product_risk,
                controversy_level,
                fact_check_needed,
                recommended_action,
                opportunity_reason,
                original_angle_ideas,
                production_priority_score,
                analysis_schema_version,
                raw_json
            FROM ai_video_analysis
            WHERE video_id = ?
            """,
            (video_id,),
        ).fetchone()

    return _row_to_analysis_dict(row)


def fetch_top_videos(db_path: str, limit: int = 100) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                videos.video_id AS video_id,
                videos.title AS title,
                videos.description AS description,
                videos.tags AS tags,
                videos.category_id AS category_id,
                videos.default_language AS default_language,
                videos.default_audio_language AS default_audio_language,
                videos.discovery_source AS discovery_source,
                videos.discovery_query AS discovery_query,
                videos.candidate_niche AS candidate_niche,
                videos.channel_id AS channel_id,
                videos.channel_title AS channel_title,
                videos.published_at AS published_at,
                videos.views AS views,
                videos.likes AS likes,
                videos.comments AS comments,
                videos.duration_seconds AS duration_seconds,
                videos.url AS url,
                videos.keyword AS keyword,
                videos.niche AS niche,
                videos.views_per_day AS views_per_day,
                videos.comment_rate AS comment_rate,
                videos.dark_friendly_score AS dark_friendly_score,
                videos.niche_relevance_score AS niche_relevance_score,
                videos.opportunity_score AS opportunity_score,
                videos.viral_tier AS viral_tier,
                videos.is_viral_candidate AS is_viral_candidate,
                videos.collected_at AS collected_at,
                analysis.is_good_reference,
                analysis.detected_language,
                analysis.source_language,
                analysis.target_market,
                analysis.real_niche,
                analysis.content_category,
                analysis.content_type,
                analysis.content_format,
                analysis.adaptation_type,
                analysis.hook_type,
                analysis.retention_pattern,
                analysis.dark_channel_fit,
                analysis.creator_fit_score,
                analysis.localization_potential,
                analysis.cultural_fit_br,
                analysis.evergreen_score,
                analysis.production_difficulty,
                analysis.originality_requirement,
                analysis.copyright_risk,
                analysis.reused_content_risk,
                analysis.source_dependency_risk,
                analysis.ip_risk,
                analysis.brand_or_product_risk,
                analysis.controversy_level,
                analysis.fact_check_needed,
                analysis.recommended_action,
                analysis.opportunity_reason,
                analysis.original_angle_ideas,
                analysis.production_priority_score,
                analysis.analysis_schema_version,
                analysis.analyzed_at,
                analysis.model
            FROM videos
            LEFT JOIN ai_video_analysis AS analysis ON analysis.video_id = videos.video_id
            ORDER BY videos.opportunity_score DESC, videos.views_per_day DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [_normalize_video_record(dict(row)) for row in rows]


def fetch_top_videos_balanced(
    db_path: str, per_niche: int = 5, total_limit: int = 25
) -> list[dict]:
    fetch_limit = max(total_limit * per_niche, total_limit * 5)

    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                videos.video_id AS video_id,
                videos.title AS title,
                videos.description AS description,
                videos.tags AS tags,
                videos.category_id AS category_id,
                videos.default_language AS default_language,
                videos.default_audio_language AS default_audio_language,
                videos.discovery_source AS discovery_source,
                videos.discovery_query AS discovery_query,
                videos.candidate_niche AS candidate_niche,
                videos.channel_id AS channel_id,
                videos.channel_title AS channel_title,
                videos.published_at AS published_at,
                videos.views AS views,
                videos.likes AS likes,
                videos.comments AS comments,
                videos.duration_seconds AS duration_seconds,
                videos.url AS url,
                videos.keyword AS keyword,
                videos.niche AS niche,
                videos.views_per_day AS views_per_day,
                videos.comment_rate AS comment_rate,
                videos.dark_friendly_score AS dark_friendly_score,
                videos.niche_relevance_score AS niche_relevance_score,
                videos.opportunity_score AS opportunity_score,
                videos.viral_tier AS viral_tier,
                videos.is_viral_candidate AS is_viral_candidate,
                videos.collected_at AS collected_at,
                analysis.is_good_reference,
                analysis.detected_language,
                analysis.source_language,
                analysis.target_market,
                analysis.real_niche,
                analysis.content_category,
                analysis.content_type,
                analysis.content_format,
                analysis.adaptation_type,
                analysis.hook_type,
                analysis.retention_pattern,
                analysis.dark_channel_fit,
                analysis.creator_fit_score,
                analysis.localization_potential,
                analysis.cultural_fit_br,
                analysis.evergreen_score,
                analysis.production_difficulty,
                analysis.originality_requirement,
                analysis.copyright_risk,
                analysis.reused_content_risk,
                analysis.source_dependency_risk,
                analysis.ip_risk,
                analysis.brand_or_product_risk,
                analysis.controversy_level,
                analysis.fact_check_needed,
                analysis.recommended_action,
                analysis.opportunity_reason,
                analysis.original_angle_ideas,
                analysis.production_priority_score,
                analysis.analysis_schema_version,
                analysis.analyzed_at,
                analysis.model
            FROM videos
            LEFT JOIN ai_video_analysis AS analysis ON analysis.video_id = videos.video_id
            ORDER BY videos.opportunity_score DESC, videos.views_per_day DESC
            LIMIT ?
            """,
            (fetch_limit,),
        ).fetchall()

    results = []
    per_niche_count: dict[str, int] = {}

    for row in rows:
        record = _normalize_video_record(dict(row))
        niche = record.get("niche")
        if not niche:
            continue

        if per_niche_count.get(niche, 0) >= per_niche:
            continue

        results.append(record)
        per_niche_count[niche] = per_niche_count.get(niche, 0) + 1

        if len(results) >= total_limit:
            break

    return results


def fetch_videos_for_ai_analysis(db_path: str, limit: int = 20, viral_only: bool = False) -> list[dict]:
    fetch_limit = max(limit * 6, 60)

    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                videos.video_id,
                videos.title,
                videos.description,
                videos.tags,
                videos.category_id,
                videos.default_language,
                videos.default_audio_language,
                videos.discovery_source,
                videos.discovery_query,
                videos.candidate_niche,
                videos.channel_id,
                videos.channel_title,
                videos.published_at,
                videos.views,
                videos.likes,
                videos.comments,
                videos.duration_seconds,
                videos.url,
                videos.keyword,
                videos.niche,
                videos.views_per_day,
                videos.comment_rate,
                videos.dark_friendly_score,
                videos.niche_relevance_score,
                videos.opportunity_score,
                videos.viral_tier,
                videos.is_viral_candidate,
                videos.collected_at
            FROM videos
            LEFT JOIN ai_video_analysis AS analysis ON analysis.video_id = videos.video_id
            WHERE (
                analysis.video_id IS NULL
                OR analysis.analysis_schema_version IS NULL
                OR analysis.analysis_schema_version < ?
            )
              AND (? = 0 OR videos.is_viral_candidate = 1)
            ORDER BY videos.opportunity_score DESC, videos.views_per_day DESC
            LIMIT ?
            """,
            (ANALYSIS_SCHEMA_VERSION, int(viral_only), fetch_limit),
        ).fetchall()

    candidates = [dict(row) for row in rows]
    if len(candidates) <= limit:
        return candidates

    results = []
    per_niche_count: dict[str, int] = {}
    max_per_niche = max(1, (limit + 2) // 3)

    for video in candidates:
        niche = video.get("niche") or "Sem nicho"
        if per_niche_count.get(niche, 0) >= max_per_niche:
            continue

        results.append(video)
        per_niche_count[niche] = per_niche_count.get(niche, 0) + 1

        if len(results) >= limit:
            return results

    for video in candidates:
        if any(saved["video_id"] == video["video_id"] for saved in results):
            continue

        results.append(video)
        if len(results) >= limit:
            break

    return results
