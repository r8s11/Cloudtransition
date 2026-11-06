"""Design-contract regression tests for the Orizuru visual system.

These gate the specific regressions that the audit found: muted-ink contrast
falling below WCAG AA, blanket `prefers-reduced-motion` overrides killing the
sanctioned crease animation, and layout-property transitions re-introducing
jank. Deterministic, isolated, full-suite-safe.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STYLE = (ROOT / "static" / "style.css").read_text()
READER = (ROOT / "templates" / "reader.html").read_text()
INDEX = (ROOT / "templates" / "index.html").read_text()


def _hex_ratio(fg: str, bg: str) -> float:
    """WCAG 2.1 relative luminance ratio for two #rrggbb values."""
    f = [int(fg.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    b = [int(bg.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    lfg = sum(lin(c) * w for c, w in zip(f, (0.2126, 0.7152, 0.0722), strict=True))
    lbg = sum(lin(c) * w for c, w in zip(b, (0.2126, 0.7152, 0.0722), strict=True))
    return (max(lfg, lbg) + 0.05) / (min(lfg, lbg) + 0.05)


def _token(name: str, source: str = STYLE) -> str:
    match = re.search(rf"--{name}:\s*(#[0-9a-fA-F]{{6}})", source)
    assert match, f"--{name} not found"
    return match.group(1)


def _paper_surfaces() -> list[str]:
    """Every washi face the muted ink renders on."""
    return [
        _token("paper"),
        _token("paper-deep"),
        _token("paper-hi"),
        _token("fold-white"),
    ]


def test_muted_ink_passes_wcag_aa_on_every_washi_face():
    fg = _token("ink-muted")
    worst = min(_hex_ratio(fg, bg) for bg in _paper_surfaces())
    assert worst >= 4.5, f"{fg} on washi faces is {worst:.2f}:1, needs 4.5:1"


def test_muted_ink_is_consistent_across_style_and_reader():
    """reader.html carries its own duplicate token; both must agree."""
    reader_token = _token("text-muted", READER)
    style_token = _token("ink-muted", STYLE)
    assert reader_token == style_token, (
        f"reader --text-muted {reader_token} != style --ink-muted {style_token}"
    )


def test_no_blanket_reduced_motion_wildcard():
    """The `*: 0.01ms` kill removed the crease animation entirely."""
    assert "0.01ms" not in STYLE, (
        "blanket prefers-reduced-motion wildcard still present"
    )
    assert "prefers-reduced-motion: reduce" in STYLE
    # Targeted overrides survive so the sanctioned animation still has a path.
    # Formatter expands one-liners; normalize whitespace before matching.
    flat = re.sub(r"\s+", " ", STYLE)
    assert ".page.active { animation: none; }" in flat
    assert ".progress-fill { transition: none; }" in flat


def test_no_layout_property_transitions():
    """width/height/margin/padding transitions thrash layout."""
    bad = re.findall(
        r"transition:\s*(?:[^;]*?\b(?:width|height|margin|padding|top|left|right|bottom)\b)",
        STYLE,
    )
    assert not bad, f"layout-property transitions: {bad}"


def test_progress_bar_uses_transform_not_width():
    assert "transform: scaleX(0)" in STYLE
    assert "transform-origin: left center" in STYLE
    assert "transition: transform" in STYLE
    # The driver must scale, not set width.
    js = (ROOT / "static" / "app.js").read_text()
    assert 'el.style.transform = "scaleX(' in js


def test_project_card_uses_token_not_inline_color():
    """Inline `{{ p.color }}` was the last hard-coded color in overview."""
    overview = (ROOT / "templates" / "pages" / "overview.html").read_text()
    assert "var(--accent)" in overview
    assert "border-left: 4px solid {{ p.color }}" not in overview
