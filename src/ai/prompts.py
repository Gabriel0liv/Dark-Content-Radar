from __future__ import annotations

import json

ANALYSIS_SYSTEM_PROMPT = (
    "Você é um analisador de conteúdo do YouTube. Responda apenas com JSON válido."
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
        "candidate_niche": video.get("candidate_niche", video.get("niche", "")),
        "keyword": video.get("keyword", ""),
        "discovery_source": video.get("discovery_source", ""),
        "discovery_query": video.get("discovery_query", ""),
        "content_profile": video.get("content_profile", "curiosity_ai_trends"),
        "viral_tier": video.get("viral_tier", ""),
        "views": video.get("views", 0),
        "views_per_day": video.get("views_per_day", 0),
        "comments": video.get("comments", 0),
        "duration_seconds": video.get("duration_seconds", 0),
        "url": video.get("url", ""),
    }


def _prompt_instructions() -> str:
    return """
Você está avaliando se um item de conteúdo do YouTube Shorts vale como referência estratégica para criar um vídeo original, narrado com voz própria, roteiro próprio e adaptação própria, para público brasileiro/português.

Objetivo:
- analisar assunto, formato provável, gancho, potencial de produção e riscos
- decidir se vale como referência para criar conteúdo original com abordagem própria
- não clonar o vídeo
- pode usar o mesmo assunto, fato, tendência ou notícia como ponto de partida, mas não copie roteiro, frases, edição, sequência narrativa, imagens, exemplos únicos ou abordagem do vídeo original. Crie uma versão original com pesquisa, voz e estrutura próprias.
- não sugerir plágio
- não depender de scraping, TikTok ou download do vídeo
- a análise é baseada apenas em metadados da YouTube Data API
- não afirme que você viu o vídeo
- você pode inferir formato provável, mas com cautela e deixando implícito que é uma inferência baseada em metadados

Regras obrigatórias:
- Responda apenas com JSON válido.
- Conteúdo em inglês ou espanhol NÃO deve ser rejeitado automaticamente. Avalie se pode ser transformado em conteúdo original para público BR/PT.
- Reduza prioridade ou rejeite quando o item depender fortemente de IP protegido, fandom, filme/série/anime/game, celebridade/fofoca local pouco relevante, legislação estrangeira muito específica, piada intraduzível, produto/anúncio, trend sem contexto para o Brasil, ou da necessidade de copiar imagens, edição ou narrativa do vídeo original.
- Ferramenta/tecnologia pode ser válida como assunto editorial se o foco for tendência, impacto, curiosidade, risco, utilidade ou novidade.
- Rejeite ferramenta/app apenas quando parecer anúncio direto, afiliado, venda, promoção ou demonstração de produto sem valor editorial.
- "recommended_action" deve ser decisivo. Use "needs_manual_review" apenas quando houver incerteza real; não use como padrão.
- Para conteúdo bom que precisa adaptação, localização ou pesquisa, use "adapt_with_research" em vez de "needs_manual_review".
- Para conteúdo genérico ou fora do perfil editorial, use "reject_low_relevance" ou "reject_low_quality".
- Para tutorial DIY/lifehack genérico fora do perfil curiosity_ai_trends, reduza "creator_fit_score" e "localization_potential" e use "reject_low_relevance" ou "needs_manual_review" com pontuações baixas.
- Para conteúdo de produto/app/promocional, use "reject_promotional".
- Use "use_as_reference" quando o item já for uma boa referência direta para vídeo original.
- Use "adapt_with_research" quando o assunto for bom, mas precisar de pesquisa, localização ou mudança de abordagem.
- Use "reject_ip_risk" para IP/fandom/filme/série/anime/game/clip.
- Use "reject_promotional" para anúncio, app/produto promocional, afiliado, venda ou demonstração sem valor editorial.
- Use "reject_too_contextual" quando depender demais de contexto local estrangeiro, celebridade específica, legislação local ou piada intraduzível.
- Use "reject_low_relevance" quando o tema estiver pouco alinhado ao perfil editorial.
- Use "reject_low_quality" quando o tema for fraco, genérico, sem gancho ou sem potencial narrativo.
- "original_angle_ideas" deve trazer apenas ângulos originais inspirados no padrão, nunca cópia do vídeo.
- "dark_channel_fit" é uma nota de 0 a 100.
- "creator_fit_score" é uma nota de 0 a 100 sobre o potencial para um vídeo original com voz e estilo próprios.
- "production_difficulty" deve ser "low", "medium" ou "high".
- "copyright_risk" deve ser "low", "medium" ou "high".
- "reused_content_risk" deve ser "low", "medium" ou "high".
- "source_language" e "detected_language" devem ser "pt", "en", "es" ou "unknown".

Perfis editoriais:
- general: aceita oportunidades amplas.
- curiosity_ai_trends: prioriza curiosidades, IA, tecnologia, ciência estranha, assuntos em alta, comportamento humano, temas polêmicos e histórias explicáveis em vídeo narrado. Reduz prioridade de DIY genérico, economia doméstica simples, app promocional, lifehack fraco e conteúdo muito local/contextual.
- finance: prioriza finanças pessoais, economia, dinheiro, trabalho, renda, impostos e educação financeira.
- history_mystery: prioriza história, mistérios, fatos bizarros, casos reais e ciência estranha.
- psychology_behavior: prioriza comportamento humano, psicologia, cérebro, relações sociais e fenômenos mentais.
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
  "source_language": "en",
  "detected_language": "en",
  "target_market": "BR",
  "real_niche": "...",
  "content_category": "ai_tech",
  "content_type": "...",
  "content_format": "short_explainer",
  "adaptation_type": "foreign_adaptable",
  "hook_type": "...",
  "retention_pattern": "...",
  "dark_channel_fit": 70,
  "creator_fit_score": 85,
  "localization_potential": 90,
  "cultural_fit_br": 80,
  "evergreen_score": 75,
  "production_difficulty": "low",
  "originality_requirement": "high",
  "copyright_risk": "low",
  "reused_content_risk": "medium",
  "source_dependency_risk": "medium",
  "ip_risk": "low",
  "brand_or_product_risk": "low",
  "controversy_level": "medium",
  "fact_check_needed": true,
  "recommended_action": "adapt_with_research",
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
      "source_language": "en",
      "detected_language": "en",
      "target_market": "BR",
      "real_niche": "...",
      "content_category": "ai_tech",
      "content_type": "...",
      "content_format": "short_explainer",
      "adaptation_type": "foreign_adaptable",
      "hook_type": "...",
      "retention_pattern": "...",
      "dark_channel_fit": 70,
      "creator_fit_score": 85,
      "localization_potential": 90,
      "cultural_fit_br": 80,
      "evergreen_score": 75,
      "production_difficulty": "low",
      "originality_requirement": "high",
      "copyright_risk": "low",
      "reused_content_risk": "medium",
      "source_dependency_risk": "medium",
      "ip_risk": "low",
      "brand_or_product_risk": "low",
      "controversy_level": "medium",
      "fact_check_needed": true,
      "recommended_action": "adapt_with_research",
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
