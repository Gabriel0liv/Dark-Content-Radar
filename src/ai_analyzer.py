from src.ai.gemini_provider import GeminiProvider


def analyze_video_opportunity(api_key: str, model: str, video: dict) -> dict:
    provider = GeminiProvider(api_key=api_key, model=model)
    return provider.analyze_video_opportunity(video)


def analyze_video_opportunities_batch(
    api_key: str, model: str, videos: list[dict]
) -> list[dict]:
    provider = GeminiProvider(api_key=api_key, model=model)
    return provider.analyze_video_opportunities_batch(videos)
