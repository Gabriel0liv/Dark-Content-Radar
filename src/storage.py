import json
import sqlite3
from pathlib import Path
from typing import Iterable


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
                collected_at TEXT
            )
            """)
        _ensure_column(conn, "videos", "niche_relevance_score", "REAL DEFAULT 0")
        _ensure_column(conn, "videos", "description", "TEXT")
        _ensure_column(conn, "videos", "tags", "TEXT")
        _ensure_column(conn, "videos", "category_id", "TEXT")
        _ensure_column(conn, "videos", "default_language", "TEXT")
        _ensure_column(conn, "videos", "default_audio_language", "TEXT")
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
                real_niche TEXT,
                content_type TEXT,
                hook_type TEXT,
                retention_pattern TEXT,
                dark_channel_fit INTEGER,
                production_difficulty TEXT,
                copyright_risk TEXT,
                reused_content_risk TEXT,
                fact_check_needed INTEGER,
                opportunity_reason TEXT,
                original_angle_ideas TEXT,
                production_priority_score REAL DEFAULT 0,
                raw_json TEXT,
                FOREIGN KEY(video_id) REFERENCES videos(video_id)
            )
            """)
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
        payloads.append(payload)

    with get_connection(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO videos (
                video_id, title, description, tags, category_id, default_language,
                default_audio_language, channel_id, channel_title, published_at,
                views, likes, comments, duration_seconds, url,
                keyword, niche, views_per_day, comment_rate,
                dark_friendly_score, niche_relevance_score, opportunity_score, collected_at
            )
            VALUES (
                :video_id, :title, :description, :tags, :category_id, :default_language,
                :default_audio_language, :channel_id, :channel_title, :published_at,
                :views, :likes, :comments, :duration_seconds, :url,
                :keyword, :niche, :views_per_day, :comment_rate,
                :dark_friendly_score, :niche_relevance_score, :opportunity_score, :collected_at
            )
            ON CONFLICT(video_id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                tags = excluded.tags,
                category_id = excluded.category_id,
                default_language = excluded.default_language,
                default_audio_language = excluded.default_audio_language,
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
                collected_at = excluded.collected_at
            """,
            payloads,
        )
        conn.commit()


def save_ai_analysis(db_path: str, analysis: dict) -> None:
    payload = dict(analysis)
    payload["is_good_reference"] = int(bool(payload.get("is_good_reference")))
    payload["fact_check_needed"] = int(bool(payload.get("fact_check_needed")))

    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO ai_video_analysis (
                video_id,
                analyzed_at,
                model,
                is_good_reference,
                detected_language,
                real_niche,
                content_type,
                hook_type,
                retention_pattern,
                dark_channel_fit,
                production_difficulty,
                copyright_risk,
                reused_content_risk,
                fact_check_needed,
                opportunity_reason,
                original_angle_ideas,
                production_priority_score,
                raw_json
            )
            VALUES (
                :video_id,
                :analyzed_at,
                :model,
                :is_good_reference,
                :detected_language,
                :real_niche,
                :content_type,
                :hook_type,
                :retention_pattern,
                :dark_channel_fit,
                :production_difficulty,
                :copyright_risk,
                :reused_content_risk,
                :fact_check_needed,
                :opportunity_reason,
                :original_angle_ideas,
                :production_priority_score,
                :raw_json
            )
            ON CONFLICT(video_id) DO UPDATE SET
                analyzed_at = excluded.analyzed_at,
                model = excluded.model,
                is_good_reference = excluded.is_good_reference,
                detected_language = excluded.detected_language,
                real_niche = excluded.real_niche,
                content_type = excluded.content_type,
                hook_type = excluded.hook_type,
                retention_pattern = excluded.retention_pattern,
                dark_channel_fit = excluded.dark_channel_fit,
                production_difficulty = excluded.production_difficulty,
                copyright_risk = excluded.copyright_risk,
                reused_content_risk = excluded.reused_content_risk,
                fact_check_needed = excluded.fact_check_needed,
                opportunity_reason = excluded.opportunity_reason,
                original_angle_ideas = excluded.original_angle_ideas,
                production_priority_score = excluded.production_priority_score,
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
                real_niche,
                content_type,
                hook_type,
                retention_pattern,
                dark_channel_fit,
                production_difficulty,
                copyright_risk,
                reused_content_risk,
                fact_check_needed,
                opportunity_reason,
                original_angle_ideas,
                production_priority_score,
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
                videos.collected_at AS collected_at,
                analysis.is_good_reference,
                analysis.detected_language,
                analysis.real_niche,
                analysis.content_type,
                analysis.hook_type,
                analysis.retention_pattern,
                analysis.dark_channel_fit,
                analysis.production_difficulty,
                analysis.copyright_risk,
                analysis.reused_content_risk,
                analysis.fact_check_needed,
                analysis.opportunity_reason,
                analysis.original_angle_ideas,
                analysis.production_priority_score,
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
                videos.collected_at AS collected_at,
                analysis.is_good_reference,
                analysis.detected_language,
                analysis.real_niche,
                analysis.content_type,
                analysis.hook_type,
                analysis.retention_pattern,
                analysis.dark_channel_fit,
                analysis.production_difficulty,
                analysis.copyright_risk,
                analysis.reused_content_risk,
                analysis.fact_check_needed,
                analysis.opportunity_reason,
                analysis.original_angle_ideas,
                analysis.production_priority_score,
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


def fetch_videos_for_ai_analysis(db_path: str, limit: int = 20) -> list[dict]:
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
                videos.collected_at
            FROM videos
            LEFT JOIN ai_video_analysis AS analysis ON analysis.video_id = videos.video_id
            WHERE analysis.video_id IS NULL
            ORDER BY videos.opportunity_score DESC, videos.views_per_day DESC
            LIMIT ?
            """,
            (fetch_limit,),
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
