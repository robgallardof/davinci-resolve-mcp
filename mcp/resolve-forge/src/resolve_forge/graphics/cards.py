"""Text cards rendered as full-frame transparent PNGs: on-screen titles and burned-in captions.

Full-frame means no positioning math in Resolve: the card already sits inside the platform's
safe zone at the timeline resolution. Colour emoji are drawn with the system emoji font.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..domain.formats import SafeZone

_FONT_DIRS = [Path(r"C:\Windows\Fonts"), Path("/System/Library/Fonts"), Path("/Library/Fonts"),
              Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts/TTF")]
_HEAVY = ["seguibl.ttf", "arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"]
_EMOJI = ["seguiemj.ttf"]  # colour emoji on Windows; elsewhere emoji are dropped rather than drawn as boxes


@dataclass(frozen=True)
class CardStyle:
    name: str
    text: tuple[int, int, int, int]
    box: tuple[int, int, int, int] | None = None   # rounded background
    stroke: tuple[int, int, int, int] | None = None
    stroke_ratio: float = 0.0                      # stroke width as a fraction of font size
    size_ratio: float = 0.06                       # font size as a fraction of the frame's short side


STYLES: dict[str, CardStyle] = {s.name: s for s in (
    CardStyle("box", text=(10, 10, 10, 255), box=(255, 255, 255, 240)),                       # TikTok-native title
    CardStyle("outline", text=(255, 255, 255, 255), stroke=(0, 0, 0, 255), stroke_ratio=0.1),  # classic captions
    CardStyle("yellow", text=(255, 221, 0, 255), stroke=(0, 0, 0, 255), stroke_ratio=0.1),    # emphasis captions
    CardStyle("dark", text=(255, 255, 255, 255), box=(0, 0, 0, 190)),                          # subtle lower third
)}
POSITIONS = ("top", "middle", "bottom")


@lru_cache(maxsize=None)
def _find(candidates: tuple[str, ...]) -> str | None:
    for name in candidates:
        for d in _FONT_DIRS:
            if (d / name).exists():
                return str(d / name)
    return None


def _text_font(size: int):
    from PIL import ImageFont

    path = _find(tuple(_HEAVY))
    return ImageFont.truetype(path, size) if path else ImageFont.load_default(size=size)


def _emoji_font(size: int):
    from PIL import ImageFont

    path = _find(tuple(_EMOJI))
    return ImageFont.truetype(path, size) if path else None


def _is_emoji(ch: str) -> bool:
    return ord(ch) >= 0x2190 and ch not in "…–—"


class _Typesetter:
    def __init__(self, size: int):
        self.text_font = _text_font(size)
        self.emoji_font = _emoji_font(int(size * 0.94))

    def runs(self, text: str):
        out: list[list] = []
        for ch in text.replace("\ufe0f", ""):
            if _is_emoji(ch):
                if self.emoji_font is None:
                    continue
                font = self.emoji_font
            else:
                font = self.text_font
            if out and out[-1][1] is font:
                out[-1][0] += ch
            else:
                out.append([ch, font])
        return out

    def width(self, draw, text: str) -> float:
        return sum(draw.textlength(t, font=f) for t, f in self.runs(text))

    def wrap(self, draw, text: str, max_w: float) -> list[str]:
        """Balanced lines; an emoji never ends up alone on a line."""
        words: list[str] = []
        for w in text.split():
            if words and all(_is_emoji(c) or c == "\ufe0f" for c in w):
                words[-1] += " " + w
            else:
                words.append(w)
        if not words or self.width(draw, " ".join(words)) <= max_w:
            return [" ".join(words)]
        best = None
        for k in range(1, len(words)):
            a, b = " ".join(words[:k]), " ".join(words[k:])
            worst = max(self.width(draw, a), self.width(draw, b))
            if worst <= max_w and (best is None or worst < best[0]):
                best = (worst, [a, b])
        if best:
            return best[1]
        lines, cur = [], ""  # 3+ lines: greedy
        for w in words:
            trial = f"{cur} {w}".strip()
            if cur and self.width(draw, trial) > max_w:
                lines.append(cur)
                cur = w
            else:
                cur = trial
        return lines + [cur]


def render(text: str, width: int, height: int, *, style: str = "box", position: str = "top",
           safe: SafeZone = SafeZone(0.1, 0.2, 0.08, 0.08)):
    """RGBA image of the whole frame with the card placed inside the safe area."""
    from PIL import Image, ImageDraw

    if style not in STYLES:
        raise ValueError(f"unknown style '{style}'. Available: {', '.join(STYLES)}")
    if position not in POSITIONS:
        raise ValueError(f"position must be one of {', '.join(POSITIONS)}")
    st = STYLES[style]
    size = max(18, int(min(width, height) * st.size_ratio))
    ts = _Typesetter(size)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad_x, pad_y = int(size * 0.55), int(size * 0.32)
    left, right = width * safe.left, width * (1 - safe.right)
    lines = ts.wrap(draw, text, right - left - 2 * pad_x)
    line_h = int(size * 1.32)
    block_h = len(lines) * line_h + (len(lines) - 1) * pad_y
    top, bottom = height * safe.top, height * (1 - safe.bottom)
    y = {"top": top + pad_y, "middle": (top + bottom - block_h) / 2, "bottom": bottom - block_h - pad_y}[position]
    stroke = int(size * st.stroke_ratio)
    cx = (left + right) / 2
    for line in lines:
        lw = ts.width(draw, line)
        x = cx - lw / 2
        if st.box:
            draw.rounded_rectangle([x - pad_x, y - pad_y * 0.7, x + lw + pad_x, y + line_h + pad_y * 0.3],
                                   radius=int(size * 0.42), fill=st.box)
        for chunk, font in ts.runs(line):
            emoji = font is ts.emoji_font
            draw.text((x, y + (size * 0.08 if emoji else 0)), chunk, font=font, fill=st.text,
                      embedded_color=emoji, stroke_width=0 if emoji else stroke,
                      stroke_fill=st.stroke if not emoji else None)
            x += draw.textlength(chunk, font=font)
        y += line_h + pad_y
    return img
