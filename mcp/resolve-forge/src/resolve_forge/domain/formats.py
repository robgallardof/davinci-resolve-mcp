"""Delivery formats per platform. Data only — services read it, nothing mutates it."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SafeZone:
    """Fractions of the frame covered by platform UI. Keep faces/text inside the rest."""
    top: float
    bottom: float
    left: float
    right: float

    def rect(self, width: int, height: int) -> dict[str, int]:
        x0, y0 = round(width * self.left), round(height * self.top)
        x1, y1 = round(width * (1 - self.right)), round(height * (1 - self.bottom))
        return {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}


@dataclass(frozen=True)
class Format:
    key: str
    label: str
    width: int
    height: int
    fps: float
    container: str = "mp4"
    codec: str = "H264"
    max_seconds: int | None = None
    loudness_lufs: float = -14.0  # integrated; true peak -1 dBTP everywhere
    bitrate_mbps: int = 12
    safe: SafeZone = SafeZone(0, 0, 0, 0)
    notes: str = ""

    @property
    def orientation(self) -> str:
        if self.height > self.width:
            return "vertical"
        return "horizontal" if self.width > self.height else "square"

    def as_dict(self) -> dict:
        d = asdict(self)
        d["safe_rect_px"] = self.safe.rect(self.width, self.height)
        d["orientation"] = self.orientation
        return d


# Safe zones are conservative, ads-grade figures published for 2025-26 overlays
# (TikTok 240/660/120/120 px, Reels 269/672/65/65 px on 1080x1920). Organic
# posts cover less, so faces may sit a bit lower; captions/CTAs must stay inside.
_VERTICAL_META = SafeZone(0.14, 0.35, 0.06, 0.06)   # Instagram/Facebook Reels overlay
_STORIES = SafeZone(0.14, 0.20, 0.06, 0.06)         # top profile bar, bottom reply/link sticker
_FEED = SafeZone(0.04, 0.04, 0.04, 0.04)
_LANDSCAPE = SafeZone(0.05, 0.10, 0.05, 0.05)        # player controls/progress bar at the bottom

FORMATS: dict[str, Format] = {f.key: f for f in (
    # ── vertical 9:16 ────────────────────────────────────────────────────────
    Format("tiktok", "TikTok 9:16", 1080, 1920, 30, max_seconds=600, loudness_lufs=-12.0,
           safe=SafeZone(0.125, 0.344, 0.111, 0.111),
           notes="Right rail (likes/comments) and bottom caption cover the frame; face in upper-middle third."),
    Format("reels", "Instagram Reels 9:16", 1080, 1920, 30, max_seconds=180, loudness_lufs=-12.0, safe=_VERTICAL_META,
           notes="Profile grid crops to 3:4 center: keep the hook inside the central 1080x1440."),
    Format("facebook_reels", "Facebook Reels 9:16", 1080, 1920, 30, loudness_lufs=-12.0, safe=_VERTICAL_META,
           notes="Same overlay family as Instagram Reels; cross-posted Reels use the IG safe zone."),
    Format("shorts", "YouTube Shorts 9:16", 1080, 1920, 30, max_seconds=180,
           safe=SafeZone(0.10, 0.30, 0.06, 0.15), notes="Shorts playback tops out at 1080p; no reason to render above."),
    Format("stories", "Instagram/Facebook Stories 9:16", 1080, 1920, 30, max_seconds=60, safe=_STORIES,
           notes="Each story card is up to 60 s; keep CTAs above the reply bar."),
    Format("snapchat", "Snapchat Spotlight 9:16", 1080, 1920, 30, max_seconds=60,
           safe=SafeZone(0.08, 0.20, 0.06, 0.10)),
    # ── vertical-ish / square feed ───────────────────────────────────────────
    Format("feed_4x5", "Instagram/Facebook feed 4:5", 1080, 1350, 30, safe=_FEED,
           notes="Takes the most feed height on mobile; best reuse of vertical masters."),
    Format("square", "Square 1:1 (feeds, LinkedIn, X)", 1080, 1080, 30, safe=_FEED),
    # ── horizontal 16:9 ──────────────────────────────────────────────────────
    Format("youtube_1080", "YouTube 16:9 1080p", 1920, 1080, 30, bitrate_mbps=16, safe=_LANDSCAPE,
           notes="Bottom ~10% hosts the progress bar/captions; end-screen elements need the last 20 s."),
    Format("youtube_4k", "YouTube 16:9 2160p", 3840, 2160, 30, codec="H265", bitrate_mbps=40, safe=_LANDSCAPE,
           notes="H.265 may need Studio or a hardware encoder; falls back to H264."),
    Format("facebook_1080", "Facebook video 16:9 1080p", 1920, 1080, 30, bitrate_mbps=12, safe=_LANDSCAPE,
           notes="Autoplays muted in feed: burn in captions; first 3 s must work without sound."),
    Format("linkedin_1080", "LinkedIn video 16:9 1080p", 1920, 1080, 30, max_seconds=600, bitrate_mbps=12,
           safe=_LANDSCAPE, notes="Muted autoplay: captions mandatory. 1:1 or 4:5 often gets more feed space."),
    Format("x_1080", "X (Twitter) video 16:9 1080p", 1920, 1080, 30, bitrate_mbps=12, safe=_LANDSCAPE),
    Format("web_1080", "Web / Vimeo / presentation 16:9 1080p", 1920, 1080, 30, bitrate_mbps=16, safe=_LANDSCAPE),
)}


def by_orientation(orientation: str | None = None) -> dict[str, Format]:
    if orientation in (None, "", "all"):
        return dict(FORMATS)
    if orientation not in ("vertical", "horizontal", "square"):
        raise ValueError("orientation must be vertical, horizontal, square or all")
    return {k: f for k, f in FORMATS.items() if f.orientation == orientation}


def markdown_table() -> str:
    """The platform table used in docs/skills — generated, so docs never drift from code."""
    rows = ["| key | Plataforma | Resolución | fps | Codec | Mbps | LUFS | Safe zone (arriba/abajo/izq/der) | Máx. |",
            "|---|---|---|---|---|---|---|---|---|"]
    for f in FORMATS.values():
        z = f.safe
        rows.append(f"| `{f.key}` | {f.label} | {f.width}×{f.height} | {f.fps:g} | {f.codec} | {f.bitrate_mbps} "
                    f"| {f.loudness_lufs:g} | {z.top:.0%} / {z.bottom:.0%} / {z.left:.0%} / {z.right:.0%} "
                    f"| {f'{f.max_seconds} s' if f.max_seconds else '—'} |")
    return "\n".join(rows) + "\n"


def get(key: str) -> Format:
    try:
        return FORMATS[key]
    except KeyError:
        raise KeyError(f"unknown format '{key}'. Available: {', '.join(FORMATS)}") from None
