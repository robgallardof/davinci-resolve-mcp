# Plataformas y specs de entrega

> Generado por `python scripts/sync.py` desde `resolve_forge/domain/formats.py`. No editar a mano.

| key | Plataforma | Resolución | fps | Codec | Mbps | LUFS | Safe zone (arriba/abajo/izq/der) | Máx. |
|---|---|---|---|---|---|---|---|---|
| `tiktok` | TikTok 9:16 | 1080×1920 | 30 | H264 | 12 | -12 | 12% / 34% / 11% / 11% | 600 s |
| `reels` | Instagram Reels 9:16 | 1080×1920 | 30 | H264 | 12 | -12 | 14% / 35% / 6% / 6% | 180 s |
| `facebook_reels` | Facebook Reels 9:16 | 1080×1920 | 30 | H264 | 12 | -12 | 14% / 35% / 6% / 6% | — |
| `shorts` | YouTube Shorts 9:16 | 1080×1920 | 30 | H264 | 12 | -14 | 10% / 30% / 6% / 15% | 180 s |
| `stories` | Instagram/Facebook Stories 9:16 | 1080×1920 | 30 | H264 | 12 | -14 | 14% / 20% / 6% / 6% | 60 s |
| `snapchat` | Snapchat Spotlight 9:16 | 1080×1920 | 30 | H264 | 12 | -14 | 8% / 20% / 6% / 10% | 60 s |
| `feed_4x5` | Instagram/Facebook feed 4:5 | 1080×1350 | 30 | H264 | 12 | -14 | 4% / 4% / 4% / 4% | — |
| `square` | Square 1:1 (feeds, LinkedIn, X) | 1080×1080 | 30 | H264 | 12 | -14 | 4% / 4% / 4% / 4% | — |
| `youtube_1080` | YouTube 16:9 1080p | 1920×1080 | 30 | H264 | 16 | -14 | 5% / 10% / 5% / 5% | — |
| `youtube_4k` | YouTube 16:9 2160p | 3840×2160 | 30 | H265 | 40 | -14 | 5% / 10% / 5% / 5% | — |
| `facebook_1080` | Facebook video 16:9 1080p | 1920×1080 | 30 | H264 | 12 | -14 | 5% / 10% / 5% / 5% | — |
| `linkedin_1080` | LinkedIn video 16:9 1080p | 1920×1080 | 30 | H264 | 12 | -14 | 5% / 10% / 5% / 5% | 600 s |
| `x_1080` | X (Twitter) video 16:9 1080p | 1920×1080 | 30 | H264 | 12 | -14 | 5% / 10% / 5% / 5% | — |
| `web_1080` | Web / Vimeo / presentation 16:9 1080p | 1920×1080 | 30 | H264 | 16 | -14 | 5% / 10% / 5% / 5% | — |

Safe zone = fracción del frame tapada por la interfaz de la app. Caras, subtítulos y CTAs van dentro del resto (`list_formats` → `safe_rect_px`). True peak −1 dBTP en todas.
