from typing import List
from datetime import datetime, timezone
import os

import isodate
from googleapiclient.discovery import build


def _parse_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _duration_to_seconds(duration: str) -> int:
    try:
        parsed = isodate.parse_duration(duration)
        return int(parsed.total_seconds())
    except Exception:
        return 0


def _youtube_client(api_key: str):
    return build("youtube", "v3", developerKey=api_key)


def search_recent_short_videos(
    api_key: str,
    keyword: str,
    niche: str,
    published_after: datetime,
    region_code: str = "BR",
    relevance_language: str = "pt",
    max_results: int = 25,
    max_pages: int | None = None,
    discovery_source: str = "niche_keywords",
    discovery_query: str | None = None,
    candidate_niche: str | None = None,
) -> List[dict]:
    youtube = _youtube_client(api_key)
    max_results = max(1, min(int(max_results), 50))
    if max_pages is None:
        try:
            max_pages = int(os.getenv("MAX_SEARCH_PAGES_PER_KEYWORD", "2"))
        except ValueError:
            max_pages = 2
    max_pages = max(1, max_pages)

    published_after_iso = (
        published_after.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    video_ids = []
    next_page_token = None

    for _ in range(max_pages):
        search_params = {
            "part": "id,snippet",
            "q": keyword,
            "type": "video",
            "order": "viewCount",
            "videoDuration": "short",
            "publishedAfter": published_after_iso,
            "regionCode": region_code,
            "relevanceLanguage": relevance_language,
            "maxResults": max_results,
        }
        if next_page_token:
            search_params["pageToken"] = next_page_token

        search_response = (
            youtube.search()
            .list(**search_params)
            .execute()
        )

        for item in search_response.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if video_id and video_id not in video_ids:
                video_ids.append(video_id)

        next_page_token = search_response.get("nextPageToken")
        if not next_page_token:
            break

    if not video_ids:
        return []

    results = []

    for start in range(0, len(video_ids), 50):
        batch_ids = video_ids[start : start + 50]
        videos_response = (
            youtube.videos()
            .list(
                part="snippet,statistics,contentDetails",
                id=",".join(batch_ids),
                maxResults=len(batch_ids),
            )
            .execute()
        )

        for item in videos_response.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            details = item.get("contentDetails", {})

            video_id = item["id"]
            duration_seconds = _duration_to_seconds(details.get("duration", ""))

            # Shorts atuais podem ter até 3 minutos. A API "short" ainda pode retornar vídeos até 4 min.
            if duration_seconds > 180:
                continue

            results.append(
                {
                    "video_id": video_id,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "tags": snippet.get("tags", []),
                    "category_id": snippet.get("categoryId", ""),
                    "default_language": snippet.get("defaultLanguage", ""),
                    "default_audio_language": snippet.get("defaultAudioLanguage", ""),
                    "channel_id": snippet.get("channelId", ""),
                    "channel_title": snippet.get("channelTitle", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "views": _parse_int(stats.get("viewCount")),
                    "likes": _parse_int(stats.get("likeCount")),
                    "comments": _parse_int(stats.get("commentCount")),
                    "duration_seconds": duration_seconds,
                    "url": f"https://www.youtube.com/shorts/{video_id}",
                    "keyword": keyword,
                    "niche": niche,
                    "discovery_source": discovery_source,
                    "discovery_query": discovery_query or keyword,
                    "candidate_niche": candidate_niche or niche,
                }
            )

    return results


def fetch_popular_short_videos(
    api_key: str,
    region_code: str,
    video_category_id: str | None = None,
    max_results: int = 50,
    pages: int = 1,
) -> List[dict]:
    youtube = _youtube_client(api_key)
    max_results = max(1, min(int(max_results), 50))
    pages = max(1, int(pages))
    next_page_token = None
    results = []

    for _ in range(pages):
        request = {
            "part": "snippet,statistics,contentDetails",
            "chart": "mostPopular",
            "regionCode": region_code,
            "maxResults": max_results,
        }
        if video_category_id:
            request["videoCategoryId"] = str(video_category_id)
        if next_page_token:
            request["pageToken"] = next_page_token

        response = youtube.videos().list(**request).execute()

        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            details = item.get("contentDetails", {})
            video_id = item["id"]
            duration_seconds = _duration_to_seconds(details.get("duration", ""))
            if duration_seconds <= 0 or duration_seconds > 180:
                continue

            discovery_query = f"mostPopular:{region_code}:{video_category_id or 'all'}"
            results.append(
                {
                    "video_id": video_id,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "tags": snippet.get("tags", []),
                    "category_id": snippet.get("categoryId", ""),
                    "default_language": snippet.get("defaultLanguage", ""),
                    "default_audio_language": snippet.get("defaultAudioLanguage", ""),
                    "channel_id": snippet.get("channelId", ""),
                    "channel_title": snippet.get("channelTitle", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "views": _parse_int(stats.get("viewCount")),
                    "likes": _parse_int(stats.get("likeCount")),
                    "comments": _parse_int(stats.get("commentCount")),
                    "duration_seconds": duration_seconds,
                    "url": f"https://www.youtube.com/shorts/{video_id}",
                    "keyword": discovery_query,
                    "niche": "YouTube popular",
                    "discovery_source": "youtube_popular",
                    "discovery_query": discovery_query,
                    "candidate_niche": "YouTube popular",
                }
            )

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return results
