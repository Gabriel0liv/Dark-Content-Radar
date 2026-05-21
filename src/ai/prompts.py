from __future__ import annotations

import json

ANALYSIS_SYSTEM_PROMPT = (
    "Você é um analisador de vídeos do YouTube. Responda apenas com JSON válido."
)


def _video_metadata(video: dict) -> dict:
    return {
        "video_id": video.get("video_id", ""),
        "title": video.get("title", ""),
        "description": video.get("description", ""),
        "tags": video.get("tags", []),
        "category_id": video.get("category_id", ""),
        "default_language": video.get("default_language", ""),
        "default_audio_language": video.get("default_audio_language", ""),
        "channel_title": video.get("channel_title", ""),
        "niche": video.get("niche", ""),
        "keyword": video.get("keyword", ""),
        "views": video.get("views", 0),
        "views_per_day": video.get("views_per_day", 0),
        "comments": video.get("comments", 0),
        "duration_seconds": video.get("duration_seconds", 0),
        "url": video.get("url", ""),
    }


def _prompt_instructions() -> str:
    return """
Você está avaliando se um vídeo do YouTube Shorts vale como referência estratégica para um canal dark em português (PT-BR/PT-PT).

Objetivo:
- analisar padrões, formato, gancho e oportunidade
- decidir se vale como referência para criar conteúdo original
- não clonar o vídeo
- não copiar o tema exato
- não sugerir plágio
- não depender de scraping, TikTok ou download do vídeo
- a análise é baseada apenas em metadados da YouTube Data API
- não afirme que você viu o vídeo
- você pode inferir formato provável, mas com cautela e deixando implícito que é uma inferência baseada em metadados

Regras obrigatórias:
- Responda apenas com JSON válido.
- Se o vídeo estiver em espanhol ou inglês, marque "is_good_reference" como false, exceto se o padrão for claramente adaptável para português.
- Se parecer gaming, fandom, trecho de série/filme, notícia política, produto/anúncio ou conteúdo dependente de imagem protegida, marque "is_good_reference" como false.
- Se for curiosidade genérica, insight, lista factual, psicologia, mistério, história, comportamento humano ou padrão adaptável para canal dark, pode marcar true.
- "original_angle_ideas" deve trazer apenas ângulos originais inspirados no padrão, nunca cópia do vídeo.
- "dark_channel_fit" é uma nota de 0 a 100.
- "production_difficulty" deve ser "low", "medium" ou "high".
- "copyright_risk" deve ser "low", "medium" ou "high".
- "reused_content_risk" deve ser "low", "medium" ou "high".
- "detected_language" deve ser "pt", "en", "es" ou "unknown".
""".strip()


def build_single_video_prompt(video: dict) -> str:
    metadata = _video_metadata(video)
    return f"""
{_prompt_instructions()}

Vídeo para análise:
{json.dumps(metadata, ensure_ascii=False, indent=2)}

Formato obrigatório:
{{
  "video_id": "...",
  "is_good_reference": true,
  "detected_language": "pt",
  "real_niche": "...",
  "content_type": "...",
  "hook_type": "...",
  "retention_pattern": "...",
  "dark_channel_fit": 85,
  "production_difficulty": "low",
  "copyright_risk": "low",
  "reused_content_risk": "low",
  "fact_check_needed": true,
  "opportunity_reason": "...",
  "original_angle_ideas": ["...", "...", "..."]
}}
""".strip()


def build_batch_video_prompt(videos: list[dict]) -> str:
    metadata = [_video_metadata(video) for video in videos]
    return f"""
{_prompt_instructions()}

Vídeos para análise:
{json.dumps(metadata, ensure_ascii=False, indent=2)}

Formato obrigatório:
{{
  "analyses": [
    {{
      "video_id": "...",
      "is_good_reference": true,
      "detected_language": "pt",
      "real_niche": "...",
      "content_type": "...",
      "hook_type": "...",
      "retention_pattern": "...",
      "dark_channel_fit": 85,
      "production_difficulty": "low",
      "copyright_risk": "low",
      "reused_content_risk": "low",
      "fact_check_needed": true,
      "opportunity_reason": "...",
      "original_angle_ideas": ["...", "...", "..."]
    }}
  ]
}}

Regras adicionais para o batch:
- Retorne uma análise para cada video_id enviado.
- Preserve o mesmo video_id de entrada.
- Se faltar algum item, responda com o máximo possível dos itens restantes.
""".strip()
