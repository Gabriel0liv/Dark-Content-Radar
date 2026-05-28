# Portal Roadmap

## Visao futura

O projeto deve evoluir de radar de videos para portal de inteligencia de conteudo. A unidade principal deixa de ser apenas um video do YouTube e passa a ser um topico ou assunto que pode receber sinais de varias fontes.

Fluxo futuro desejado:

`source collection -> topic clustering -> opportunity scoring -> brief -> roteiro -> producao`

## Entidades futuras

- `source_items`: itens brutos coletados de YouTube, X/Twitter, Reddit, Google Trends, RSS e outras fontes.
- `topics`: assuntos consolidados a partir de varios sinais.
- `topic_items`: tabela de associacao entre topicos e itens de origem.
- `content_opportunities`: oportunidades priorizadas para producao.
- `content_briefs`: briefs editoriais derivados das oportunidades.
- `scripts`: roteiros gerados ou produzidos manualmente.
- `publication_tracking`: acompanhamento de producao, publicacao e performance.

## Fontes futuras

- YouTube
- X/Twitter
- Reddit
- Google Trends
- RSS/noticias
- Product Hunt/Hacker News para IA e tecnologia

## Compatibilidade com o presente

- Os videos atuais do YouTube serao tratados futuramente como `source_items`.
- `videos` e `ai_video_analysis` continuam sendo o modelo operacional atual.
- Nenhuma das tabelas futuras sera implementada nesta etapa.
- O objetivo agora e preparar o contrato de analise, o score e a interface para uma transicao gradual.
