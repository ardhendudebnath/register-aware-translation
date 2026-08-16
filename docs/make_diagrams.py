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


#: The origin currently in force. Each diagram places its block differently, so
#: builders swap this with :func:`using_origin` rather than threading an origin
#: argument through every helper.
_ORIGIN = ORIGIN


class using_origin:
    """Temporarily move the projection origin, for one diagram."""

    def __init__(self, x: float, y: float):
        self._new = (x, y)
        self._old = _ORIGIN

    def __enter__(self):
        global _ORIGIN
        self._old = _ORIGIN
        _ORIGIN = self._new
        return self

    def __exit__(self, *exc):
        global _ORIGIN
        _ORIGIN = self._old
        return False


def project(x: float, y: float, z: float) -> Tuple[float, float]:
    """World (x, y, z) -> screen. z is up."""
    sx = (x - y) * _COS30
    sy = (x + y) * _SIN30 - z
    return _ORIGIN[0] + sx * SCALE, _ORIGIN[1] + sy * SCALE


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


def _svg_open(W: float, H: float, theme: Theme, aria: str) -> List[str]:
    """Opening tag, shared defs and background."""
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" '
        f'width="{W:.0f}" height="{H:.0f}" role="img" aria-label="{_escape(aria)}">',
        f'<defs>'
        f'<marker id="arrowhead-{theme.name}" markerWidth="9" markerHeight="7" '
        f'refX="8" refY="3.5" orient="auto">'
        f'<polygon points="0 0, 9 3.5, 0 7" fill="{theme.arrow}"/></marker>'
        f'<filter id="soft-{theme.name}" x="-25%" y="-25%" width="150%" height="150%">'
        f'<feDropShadow dx="0" dy="6" stdDeviation="7" flood-opacity="0.16"/></filter>'
        f'</defs>',
        f'<rect width="{W:.0f}" height="{H:.0f}" fill="{theme.bg}"/>',
    ]


def _title(x: float, y: float, title: str, subtitle: str, theme: Theme) -> List[str]:
    font = "system-ui,-apple-system,Segoe UI,Roboto,sans-serif"
    return [
        f'<text x="{x}" y="{y}" font-size="19" font-weight="700" fill="{theme.text}" '
        f'font-family="{font}">{_escape(title)}</text>',
        f'<text x="{x}" y="{y + 23}" font-size="13" fill="{theme.muted}" '
        f'font-family="{font}">{_escape(subtitle)}</text>',
    ]


def _flat_text(x: float, y: float, text: str, size: float, colour: str,
               weight: str = "400", anchor: str = "start",
               spacing: str = "normal") -> str:
    font = "system-ui,-apple-system,Segoe UI,Roboto,sans-serif"
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{colour}" '
        f'font-weight="{weight}" text-anchor="{anchor}" letter-spacing="{spacing}" '
        f'font-family="{font}">{_escape(text)}</text>'
    )


# ==========================================================================
# 2 — the three-stage pipeline, as a descending isometric run
# ==========================================================================


def build_pipeline(theme: Theme) -> str:
    """
    Speech in, speech out, with the three stages as stacked slabs.

    Drawn as a descending run rather than a flat left-to-right chain so the
    middle box reads as *replaceable* — it is the only stage with a different
    fill, and the two either side of it are the ones this project owns.
    """
    W, H = 1000, 470
    parts = _svg_open(W, H, theme,
                      "Setu three-stage pipeline: pre-edit, translate, register post-edit")
    parts += _title(34, 42, "Three stages — the middle one is swappable",
                    "Pre-edit and post-edit are the product. Translation is a box you can replace.",
                    theme)

    # Advancing along +x alone pushes a slab *down*-right, so a five-stage
    # chain walks straight off the bottom of the canvas. Stepping along the
    # x/-y diagonal instead keeps (x + y) constant, and therefore screen-y
    # constant, giving a level run across the page.
    stage_w = stage_d = 86.0
    stage_h = 24.0
    step = 96.0

    stages = [
        ("SPEECH IN", "mic · VAD · ASR", theme.tier, theme.text, theme.muted, False),
        ("① PRE-EDIT", "steer source", theme.client, theme.text, theme.muted, False),
        ("② TRANSLATE", "any engine", theme.tier, theme.text, theme.muted, True),
        ("③ POST-EDIT", "register here", theme.register, "#ffffff", "#dbe3ff", False),
        ("SPEECH OUT", "register prosody", theme.client, theme.text, theme.muted, False),
    ]

    with using_origin(128.0, 236.0):
        for i, (name, sub, colours, txt, sub_c, dashed) in enumerate(stages):
            x, y = i * step, -i * step
            parts.extend(slab(x, y, 0, stage_w, stage_d, stage_h, colours, theme))
            if dashed:
                # A dashed outline for the one box that is not ours.
                pts = [project(x, y, stage_h), project(x + stage_w, y, stage_h),
                       project(x + stage_w, y + stage_d, stage_h),
                       project(x, y + stage_d, stage_h)]
                pt_s = " ".join(f"{a:.2f},{b:.2f}" for a, b in pts)
                parts.append(
                    f'<polygon points="{pt_s}" fill="none" stroke="{theme.accent}" '
                    f'stroke-width="2.2" stroke-dasharray="6 4" stroke-linejoin="round"/>'
                )

            parts.extend(label(
                x + stage_w / 2, y + stage_d / 2, stage_h,
                [(name, 11, txt, "700"), (sub, 9, sub_c, "400")],
                theme,
            ))

        # Timing badges, because the point of the layer is that it is free.
        badges = {1: ("< 1 ms", theme.ok), 2: ("200-500 ms", theme.muted),
                  3: ("~1 ms · offline", theme.ok)}
        for i, (text, colour) in badges.items():
            px, py = project(i * step + stage_w / 2, -i * step + stage_d, 0)
            parts.append(_flat_text(px, py + 26, text, 10.5, colour, "600", "middle"))

    parts.append(_flat_text(
        34, H - 30,
        "The register layer never appears in the latency budget — it is a string pass.",
        12, theme.muted, "500",
    ))
    parts.append("</svg>")
    return "\n".join(parts)


# ==========================================================================
# 3 — the register ladder, as an actual staircase
# ==========================================================================


def build_ladder(theme: Theme) -> str:
    """
    The same sentence at four levels, drawn as rising steps.

    This is the five-second demo, and a staircase is the honest shape for it:
    the levels are ordered, the rise is uniform, and where a language does not
    distinguish two levels the steps sit at the same height.
    """
    W, H = 1000, 560
    parts = _svg_open(W, H, theme,
                      "The register ladder: one Bengali sentence rendered at four politeness levels")
    parts += _title(34, 42, "One sentence, four registers",
                    "Because the rule table is symmetric, the same data upgrades, downgrades and detects.",
                    theme)

    rungs = [
        ("CLOSE", "তুই কি করছিস?", "to a younger sibling"),
        ("CASUAL", "তুমি কি করছ?", "to a friend"),
        ("POLITE", "আপনি কি করছেন?", "to a stranger"),
        ("FORMAL", "আপনি কি করছেন?", "same form in Bengali"),
    ]

    # Same diagonal step as the pipeline, plus a rise in z, so the rungs climb
    # up-and-right instead of marching off the bottom of the canvas.
    tread_w = tread_d = 118.0
    tread_h = 18.0
    step = 124.0
    rise = 40.0

    with using_origin(150.0, 330.0):
        for i, (name, text, note) in enumerate(rungs):
            x, y, z = i * step, -i * step, i * rise
            # The top two rungs are identical in Bengali; tint them to say so
            # rather than pretending they are separate levels.
            colours = theme.register if i >= 2 else theme.client
            parts.extend(slab(x, y, z, tread_w, tread_d, tread_h, colours, theme))

            txt = "#ffffff" if i >= 2 else theme.text
            sub = "#dbe3ff" if i >= 2 else theme.muted
            parts.extend(label(
                x + tread_w / 2, y + tread_d / 2, z + tread_h,
                [(name, 10.5, sub, "700"), (text, 14, txt, "600"), (note, 9, sub, "400")],
                theme,
            ))

    # The three jobs one table does, in a row *under* the stairs. They used to
    # sit beside them, which collided: the staircase spans almost the full
    # width once isometric projection has spread it out.
    jobs = [
        ("upgrade", "casual → formal", theme.accent),
        ("downgrade", "formal → casual", theme.accent),
        ("detect", "read the speaker's own level", theme.ok),
    ]
    row_y = 476
    parts.append(_flat_text(34, row_y - 14, "ONE TABLE, THREE JOBS", 11,
                            theme.muted, "700", spacing="0.08em"))
    box_w, gap = 296.0, 16.0
    for i, (name, sub, colour) in enumerate(jobs):
        x = 34 + i * (box_w + gap)
        parts.append(
            f'<rect x="{x:.0f}" y="{row_y}" width="{box_w:.0f}" height="42" rx="9" '
            f'fill="{theme.tier[0]}" stroke="{theme.edge}"/>'
        )
        parts.append(_flat_text(x + 14, row_y + 18, name, 12.5, colour, "700"))
        parts.append(_flat_text(x + 14, row_y + 33, sub, 10.5, theme.muted))

    parts.append(_flat_text(
        34, H - 22,
        f"{LANGUAGE_COUNT} languages. Adding one means adding a table, not writing code — "
        "and every edit is shown to the user.",
        12, theme.muted, "500",
    ))
    parts.append("</svg>")
    return "\n".join(parts)


# ==========================================================================
# 4 — module structure, as dependency layers
# ==========================================================================


def build_modules(theme: Theme) -> str:
    """
    The packages, stacked by what depends on what.

    The shape carries the argument: ``register/`` is the widest slab and sits at
    the bottom with nothing under it, because it depends on nothing. That is
    what lets it run offline in ~1 ms and be lifted out as a component.
    """
    W, H = 1000, 560
    parts = _svg_open(W, H, theme, "Setu module structure, stacked by dependency direction")
    parts += _title(34, 42, "Dependencies point downward",
                    "register/ is at the bottom because it depends on nothing at all.",
                    theme)

    layers = [
        # (z, width, colours, title, contents)
        (0.0, 340.0, theme.register, "register/  —  zero dependencies",
         "tables · engine · boundaries · gender · speaker · selectors"),
        (58.0, 250.0, theme.tier, "models/  —  swappable backends",
         "stt · language_id · classifier · translator · tts"),
        (116.0, 250.0, theme.client, "pipeline/  —  orchestration",
         "core · conversation · relationships · learner"),
        (174.0, 160.0, theme.tier, "app.py",
         "Flask · SocketIO · REST"),
    ]

    depth = 150.0
    with using_origin(300.0, 300.0):
        for z, width, colours, name, contents in layers:
            parts.extend(slab(0, 0, z, width, depth, 30.0, colours, theme))
            is_reg = colours is theme.register
            txt = "#ffffff" if is_reg else theme.text
            sub = "#dbe3ff" if is_reg else theme.muted
            parts.extend(label(
                width / 2, depth / 2, z + 30.0,
                [(name, 12.5, txt, "700"), (contents, 9.5, sub, "400")],
                theme,
            ))

    # Callouts on the right.
    notes = [
        ("evaluation/", "register · detection · semantic preservation",
         "measures the layer, depends only on it", theme.ok),
        ("classifier/", "fine-tunes on FAME-MT",
         "optional — the engine works without it", theme.muted),
        ("data_preprocessing/", "streams 11.2M rows into splits",
         "hash-assigned, shuffled, interleaved", theme.muted),
    ]
    bx = 640
    for i, (name, what, why, colour) in enumerate(notes):
        y = 120 + i * 92
        parts.append(
            f'<rect x="{bx}" y="{y}" width="320" height="66" rx="10" '
            f'fill="{theme.tier[0]}" stroke="{theme.edge}"/>'
        )
        parts.append(_flat_text(bx + 16, y + 22, name, 12.5, colour, "700"))
        parts.append(_flat_text(bx + 16, y + 39, what, 10.5, theme.text))
        parts.append(_flat_text(bx + 16, y + 54, why, 10, theme.muted))

    parts.append(_flat_text(
        34, H - 26,
        "Nothing above the bottom slab can break it — which is why it still works with no network.",
        12, theme.muted, "500",
    ))
    parts.append("</svg>")
    return "\n".join(parts)


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


#: Every diagram the README embeds. Each is written twice, light and dark, and
#: the README picks between them with a <picture> element so the figures follow
#: GitHub's theme.
DIAGRAMS = (
    ("architecture", build),
    ("pipeline", build_pipeline),
    ("ladder", build_ladder),
    ("modules", build_modules),
)


def _in_defs(root, element) -> bool:
    """True when the element lives inside <defs> (marker/filter coordinate space)."""
    for defs in root.iter():
        if defs.tag.rsplit("}", 1)[-1] == "defs":
            for child in defs.iter():
                if child is element:
                    return True
    return False


def _check_bounds(svg: str, name: str) -> None:
    """
    Catch content drawn outside the canvas.

    An SVG with an element at x=1400 in a 1000-wide viewBox is silently clipped
    — it renders, it just quietly loses half a label. Cheap to check, and the
    isometric builders make it easy to overshoot.
    """
    import re
    import xml.etree.ElementTree as ET

    root = ET.fromstring(svg)
    vb = [float(v) for v in (root.get("viewBox") or "0 0 0 0").split()]
    if len(vb) != 4:
        raise AssertionError(f"{name}: missing viewBox")
    _, _, width, height = vb

    worst = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "text":
            x, y = float(el.get("x", 0)), float(el.get("y", 0))
            if not (-2 <= x <= width + 2) or not (-2 <= y <= height + 2):
                worst.append(f"{tag} '{(el.text or '')[:24]}' at ({x:.0f},{y:.0f})")
        elif tag == "polygon":
            # SVG allows commas and/or whitespace between numbers, and the
            # arrowhead marker uses "0 0, 9 3.5, 0 7" while the slabs use
            # "x,y x,y". Pull the numbers out and pair them rather than
            # assuming a separator.
            # Marker geometry lives in its own tiny coordinate space.
            if _in_defs(root, el):
                continue
            nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", el.get("points") or "")]
            for px, py in zip(nums[0::2], nums[1::2]):
                if not (-2 <= px <= width + 2) or not (-2 <= py <= height + 2):
                    worst.append(f"polygon point ({px:.0f},{py:.0f})")
                    break
    if worst:
        raise AssertionError(
            f"{name}: {len(worst)} element(s) outside the {width:.0f}x{height:.0f} "
            f"canvas — first: {worst[0]}"
        )


def main() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    for name, builder in DIAGRAMS:
        for theme in (LIGHT, DARK):
            svg = builder(theme)
            _check_bounds(svg, f"{name}-{theme.name}")
            path = DOCS / f"{name}-{theme.name}.svg"
            path.write_text(svg, encoding="utf-8")
            print(f"wrote {path.relative_to(DOCS.parent)}  "
                  f"({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
