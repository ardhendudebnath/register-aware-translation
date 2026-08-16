"""
Generate the isometric architecture diagram, in light and dark.

    python docs/make_diagrams.py

The diagram exists to make one structural claim legible at a glance: **the
register layer is a slab that spans every engine tier rather than sitting inside
any of them.** A flat box-and-arrow drawing cannot show that — it renders the
layer as one box among many, which is exactly the wrong intuition. Drawn as
stacked slabs in isometric projection, the load-bearing idea is the shape
itself: swap anything in the bottom row and the wide slab above is untouched.

Two files are written, and the README picks between them with a
``<picture>`` element so the diagram follows GitHub's theme.

No dependencies — this writes SVG text directly.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

DOCS = Path(__file__).resolve().parent


def _language_count() -> int:
    """
    Read the count off the tables rather than hardcoding it, so adding a
    language cannot leave the diagram quietly claiming the old number.
    """
    import sys

    sys.path.insert(0, str(DOCS.parent))
    try:
        from register import supported_languages

        return len(supported_languages())
    except Exception:
        return 20


LANGUAGE_COUNT = _language_count()

# Isometric projection. 30 degrees is the classic choice: it keeps verticals
# vertical, which means text on the top faces stays readable.
_COS30 = math.cos(math.radians(30))
_SIN30 = math.sin(math.radians(30))

SCALE = 1.0
#: Isometric projection spreads a block sideways: a 300-wide, 190-deep box
#: occupies ~425 px of screen width, centred on the origin's x. The origin is
#: therefore well left of centre so the block clears the pipeline column on the
#: right. :func:`_assert_no_overlap` checks this rather than trusting it.
ORIGIN = (250.0, 300.0)

#: Where the flat three-stage pipeline column starts.
PIPELINE_X = 620.0
PIPELINE_W = 300.0


class Theme:
    def __init__(self, name: str, **kw):
        self.name = name
        self.__dict__.update(kw)


LIGHT = Theme(
    "light",
    bg="#ffffff",
    text="#1a1d28",
    muted="#5f6780",
    edge="#c9cfe0",
    arrow="#8b93ab",
    # (top, left, right) per slab role
    client=("#dfe6ff", "#c2cdf5", "#aebbef"),
    register=("#7c9cff", "#5f83f5", "#4a70ec"),
    tier=("#f0f2f8", "#dfe3ee", "#cdd3e3"),
    accent="#3d5bd9",
    ok="#17835c",
)

DARK = Theme(
    "dark",
    bg="#0e1016",
    text="#e8eaf2",
    muted="#949bb3",
    edge="#39405a",
    arrow="#6b7391",
    client=("#2b3350", "#232a44", "#1c2238"),
    register=("#7c9cff", "#5f83f5", "#4a70ec"),
    tier=("#1e2231", "#191d2a", "#141822"),
    accent="#7c9cff",
    ok="#5ad19a",
)


def project(x: float, y: float, z: float) -> Tuple[float, float]:
    """World (x, y, z) -> screen. z is up."""
    sx = (x - y) * _COS30
    sy = (x + y) * _SIN30 - z
    return ORIGIN[0] + sx * SCALE, ORIGIN[1] + sy * SCALE


def _poly(points: Sequence[Tuple[float, float]], fill: str, stroke: str,
          width: float = 1.0, opacity: float = 1.0) -> str:
    pts = " ".join(f"{px:.2f},{py:.2f}" for px, py in points)
    return (
        f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" '
        f'stroke-width="{width}" stroke-linejoin="round" opacity="{opacity}"/>'
    )


def slab(x: float, y: float, z: float, w: float, d: float, h: float,
         colours: Tuple[str, str, str], theme: Theme) -> List[str]:
    """
    One isometric box. Returns SVG for its three visible faces, painted
    top-lightest so the solid reads as lit from above.
    """
    top_c, left_c, right_c = colours
    x1, y1, z1 = x + w, y + d, z + h

    top = [project(x, y, z1), project(x1, y, z1), project(x1, y1, z1), project(x, y1, z1)]
    left = [project(x, y1, z1), project(x1, y1, z1), project(x1, y1, z), project(x, y1, z)]
    right = [project(x1, y, z1), project(x1, y1, z1), project(x1, y1, z), project(x1, y, z)]

    return [
        _poly(left, left_c, theme.edge),
        _poly(right, right_c, theme.edge),
        _poly(top, top_c, theme.edge, 1.2),
    ]


def label(x: float, y: float, z: float, lines: Sequence[Tuple[str, int, str, str]],
          theme: Theme, anchor: str = "middle") -> List[str]:
    """Text on a top face. Each line is (text, size, colour, weight)."""
    px, py = project(x, y, z)
    out = []
    total = sum(size + 5 for _, size, _, _ in lines)
    cursor = py - total / 2 + lines[0][1]
    for text, size, colour, weight in lines:
        out.append(
            f'<text x="{px:.2f}" y="{cursor:.2f}" font-size="{size}" fill="{colour}" '
            f'font-weight="{weight}" text-anchor="{anchor}" '
            f'font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif">'
            f'{_escape(text)}</text>'
        )
        cursor += size + 5
    return out


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def arrow(p0: Tuple[float, float], p1: Tuple[float, float], theme: Theme,
          dashed: bool = False, marker: str = "arrowhead") -> str:
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    return (
        f'<line x1="{p0[0]:.2f}" y1="{p0[1]:.2f}" x2="{p1[0]:.2f}" y2="{p1[1]:.2f}" '
        f'stroke="{theme.arrow}" stroke-width="1.8"{dash} '
        f'marker-end="url(#{marker}-{theme.name})"/>'
    )


def _assert_layout(span_w: float, span_d: float, top_z: float, W: float, H: float) -> None:
    """
    Fail loudly if the isometric block runs into the pipeline column or off the
    canvas.

    Isometric projection spreads a block sideways by roughly
    ``(width + depth) * cos30``, which is easy to underestimate — the first
    version of this diagram had the block overlapping the pipeline text by
    134 px, and the overlap is invisible until something is rendered.
    """
    xs, ys = [], []
    for z in (0.0, top_z):
        for x, y in ((0, 0), (span_w, 0), (span_w, span_d), (0, span_d)):
            px, py = project(x, y, z)
            xs.append(px)
            ys.append(py)

    right = max(xs)
    if right > PIPELINE_X - 12:
        raise AssertionError(
            f"isometric block reaches x={right:.0f} but the pipeline column "
            f"starts at x={PIPELINE_X:.0f}. Move ORIGIN left or shrink the block."
        )
    if min(xs) < 8 or max(ys) > H - 8 or min(ys) < 80:
        raise AssertionError(
            f"isometric block escapes the canvas: "
            f"x {min(xs):.0f}..{right:.0f}, y {min(ys):.0f}..{max(ys):.0f} "
            f"in {W:.0f}x{H:.0f}"
        )


def build(theme: Theme) -> str:
    W, H = 1000, 580
    parts: List[str] = []

    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" '
        f'aria-label="Setu architecture: the register layer spans all three engine tiers">'
    )
    parts.append(
        f'<defs>'
        f'<marker id="arrowhead-{theme.name}" markerWidth="9" markerHeight="7" '
        f'refX="8" refY="3.5" orient="auto">'
        f'<polygon points="0 0, 9 3.5, 0 7" fill="{theme.arrow}"/></marker>'
        f'<filter id="soft-{theme.name}" x="-20%" y="-20%" width="140%" height="140%">'
        f'<feDropShadow dx="0" dy="6" stdDeviation="7" flood-opacity="0.16"/></filter>'
        f'</defs>'
    )
    parts.append(f'<rect width="{W}" height="{H}" fill="{theme.bg}"/>')

    # ---- title -------------------------------------------------------
    parts.append(
        f'<text x="34" y="42" font-size="19" font-weight="700" fill="{theme.text}" '
        f'font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif">'
        f'Setu — the register layer sits above the engine</text>'
    )
    parts.append(
        f'<text x="34" y="65" font-size="13" fill="{theme.muted}" '
        f'font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif">'
        f'Swap anything in the bottom row; everything above it is untouched.</text>'
    )

    # Geometry. One wide slab for the register layer, three small ones below.
    span_w, span_d = 300.0, 190.0
    tier_w, tier_d = 92.0, 190.0
    gap = 12.0
    _assert_layout(span_w, span_d, 184.0, W, H)

    # ---- bottom row: the three engine tiers --------------------------
    tiers = [
        ("TIER A", "Cloud API", "best quality"),
        ("TIER B", "Free public", "browser + keyless"),
        ("TIER C", "On-device", "Whisper + IndicTrans2"),
    ]
    for i, (name, what, note) in enumerate(tiers):
        x = i * (tier_w + gap)
        parts.extend(slab(x, 0, 0, tier_w, tier_d, 26, theme.tier, theme))
        parts.extend(label(
            x + tier_w / 2, tier_d / 2, 26,
            [
                (name, 11, theme.muted, "700"),
                (what, 12, theme.text, "600"),
                (note, 9, theme.muted, "400"),
            ],
            theme,
        ))

    # ---- the register layer: one slab spanning all of them ------------
    reg_z = 78.0
    parts.append(f'<g filter="url(#soft-{theme.name})">')
    parts.extend(slab(0, 0, reg_z, span_w, span_d, 40, theme.register, theme))
    parts.append("</g>")
    parts.extend(label(
        span_w / 2, span_d / 2, reg_z + 40,
        [
            ("REGISTER LAYER", 13, "#ffffff", "700"),
            ("rewrite · detect · ladder", 12, "#e8eaff", "500"),
            (f"{LANGUAGE_COUNT} languages · ~1 ms · no network", 10, "#cdd8ff", "400"),
        ],
        theme,
    ))

    # ---- client on top ------------------------------------------------
    cli_z = 152.0
    parts.extend(slab(0, 0, cli_z, span_w, span_d, 32, theme.client, theme))
    parts.extend(label(
        span_w / 2, span_d / 2, cli_z + 32,
        [
            ("CLIENT", 12, theme.muted, "700"),
            ("PWA · mic · dial · ladder", 12, theme.text, "600"),
        ],
        theme,
    ))

    # ---- side annotations ---------------------------------------------
    # Kept short on purpose: they sit between the isometric block and the
    # pipeline column, and long labels collide with the latter.
    notes = [
        (cli_z + 46, "one codebase", theme.muted),
        (reg_z + 54, "your IP", theme.accent),
        (34, "swappable", theme.muted),
    ]
    for z, text, colour in notes:
        px, py = project(span_w, span_d / 2, z)
        parts.append(
            f'<line x1="{px + 6:.2f}" y1="{py:.2f}" x2="{px + 40:.2f}" y2="{py:.2f}" '
            f'stroke="{theme.edge}" stroke-width="1.4"/>'
        )
        parts.append(
            f'<text x="{px + 46:.2f}" y="{py + 4:.2f}" font-size="12" fill="{colour}" '
            f'font-weight="600" '
            f'font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif">'
            f'{_escape(text)}</text>'
        )

    # ---- the three-stage pipeline, drawn along the top ----------------
    stages = [
        ("① pre-edit", "steer the source", theme.muted),
        ("② translate", "swappable engine", theme.muted),
        ("③ post-edit", "register applied here", theme.accent),
    ]
    base_x, base_y = PIPELINE_X, 132
    for i, (title, sub, colour) in enumerate(stages):
        y = base_y + i * 68
        boxw = PIPELINE_W
        fill = theme.register[0] if i == 2 else theme.tier[0]
        txt = "#ffffff" if i == 2 else theme.text
        sub_c = "#dbe3ff" if i == 2 else theme.muted
        parts.append(
            f'<rect x="{base_x}" y="{y}" width="{boxw}" height="50" rx="10" '
            f'fill="{fill}" stroke="{theme.edge}" stroke-width="1.2"/>'
        )
        parts.append(
            f'<text x="{base_x + 16}" y="{y + 21}" font-size="13" font-weight="700" '
            f'fill="{txt}" font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif">'
            f'{_escape(title)}</text>'
        )
        parts.append(
            f'<text x="{base_x + 16}" y="{y + 38}" font-size="11" fill="{sub_c}" '
            f'font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif">'
            f'{_escape(sub)}</text>'
        )
        if i < 2:
            parts.append(arrow((base_x + boxw / 2, y + 50), (base_x + boxw / 2, y + 66), theme))

    parts.append(
        f'<text x="{base_x}" y="{base_y - 16}" font-size="11" font-weight="700" '
        f'fill="{theme.muted}" letter-spacing="0.08em" '
        f'font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif">'
        f'THREE-STAGE PIPELINE</text>'
    )

    # ---- the payoff line ----------------------------------------------
    parts.append(
        f'<text x="{base_x}" y="{base_y + 232}" font-size="11.5" fill="{theme.ok}" '
        f'font-weight="600" '
        f'font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif">'
        f'A phrase cached at Polite re-renders at Formal</text>'
    )
    parts.append(
        f'<text x="{base_x}" y="{base_y + 249}" font-size="11.5" fill="{theme.ok}" '
        f'font-weight="600" '
        f'font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif">'
        f'with no network at all.</text>'
    )

    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    for theme, filename in ((LIGHT, "architecture-light.svg"),
                            (DARK, "architecture-dark.svg")):
        path = DOCS / filename
        path.write_text(build(theme), encoding="utf-8")
        print(f"wrote {path.relative_to(DOCS.parent)}  ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
