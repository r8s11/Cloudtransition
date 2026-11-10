"""Design-contract regression tests for the Orizuru visual system.

These gate the specific regressions that the audit found: muted-ink contrast
falling below WCAG AA, blanket `prefers-reduced-motion` overrides killing the
sanctioned crease animation, and layout-property transitions re-introducing
jank. Deterministic, isolated, full-suite-safe.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TOKENS = (ROOT / "static" / "tokens.css").read_text()
STYLE = (ROOT / "static" / "style.css").read_text()
READER = (ROOT / "templates" / "reader.html").read_text()
INDEX = (ROOT / "templates" / "index.html").read_text()

sys.path.insert(0, str(ROOT))

import app as dashboard  # noqa: E402


def _hex_ratio(fg: str, bg: str) -> float:
    """WCAG 2.1 relative luminance ratio for two #rrggbb values."""
    f = [int(fg.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    b = [int(bg.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    lfg = sum(lin(c) * w for c, w in zip(f, (0.2126, 0.7152, 0.0722), strict=True))
    lbg = sum(lin(c) * w for c, w in zip(b, (0.2126, 0.7152, 0.0722), strict=True))
    return (max(lfg, lbg) + 0.05) / (min(lfg, lbg) + 0.05)


def _token(name: str, source: str = TOKENS) -> str:
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


def test_reader_loads_shared_tokens_instead_of_duplicating_them():
    """The reader must consume tokens.css, not re-declare the palette."""
    assert "/static/tokens.css" in READER
    assert "/static/tokens.css" in INDEX
    reader_root = re.search(r":root\s*\{(.*?)\}", READER, re.S).group(1)
    for shared in (
        "--vermilion:",
        "--paper:",
        "--ink-muted:",
        "--border:",
        "--accent:",
        "--mono:",
        "--radius:",
    ):
        assert shared not in reader_root, f"reader re-declares shared token {shared}"
    assert "--surface: var(--paper-hi);" in reader_root
    assert "--accent-warm: var(--vermilion-light);" in reader_root


def test_run_state_colors_pass_wcag_aa_on_every_washi_face():
    """Run status text (yellow/green/red) must be readable on all paper faces."""
    for name in ("yellow", "green", "red"):
        fg = _token(name)
        worst = min(_hex_ratio(fg, bg) for bg in _paper_surfaces())
        assert worst >= 4.5, (
            f"run state color --{name} {fg} on washi faces is {worst:.2f}:1, needs 4.5:1"
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


def test_run_history_status_is_visible_text_not_just_a_dot():
    """The dot is aria-hidden and colour-only; the row must carry the words."""
    js = (ROOT / "static" / "app.js").read_text()
    assert 'dot.setAttribute("aria-hidden", "true")' in js
    assert "run-log-status" in js
    assert 'el("span", null, RUN_STATUS_LABELS[r.status]' in js
    assert ".run-log-status {" in STYLE


def test_run_pickers_cannot_widen_the_card():
    """Long model option names must not force horizontal overflow."""
    field = re.search(r"\.run-settings-row \.run-field \{([^}]*)\}", STYLE)
    select = re.search(r"\.run-select \{([^}]*)\}", STYLE)
    assert field and "min-width: 0" in field.group(1)
    assert select and "min-width: 0" in select.group(1)
    assert "width: 100%" in select.group(1)


def test_refresh_models_announces_success_and_failure():
    """The refresh button needs a live region; silent failures hide the cause."""
    js = (ROOT / "static" / "app.js").read_text()
    run_page = (ROOT / "templates" / "pages" / "run.html").read_text()
    assert 'id="refreshModelsStatus"' in run_page
    assert 'aria-live="polite"' in run_page
    assert '"Models refreshed."' in js
    assert '"Model refresh failed; showing the last known list."' in js
    assert '"/api/skills/catalog/refresh"' in js
    # The visible placeholder is an example, never a copy of the label.
    assert "input.placeholder = s.input_label" not in js
    assert "inputPlaceholder(s.input_label" in js


def test_run_model_picker_preselects_the_configured_model():
    """Bare Claude option values never matched the `claude:<model>` default."""
    js = (ROOT / "static" / "app.js").read_text()
    assert "option.value = `${provider}:${m.id}`;" in js
    assert 'let defaultValue = `claude:${s.model || "sonnet"}`;' in js
    assert "option.selected = option.value === defaultValue;" in js


def test_reader_reduced_motion_is_targeted_not_a_blanket_kill():
    """Reduced motion removes movement, never the state change itself."""
    assert "animation: none !important" not in READER
    assert "transition: none !important" not in READER
    block = re.search(
        r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n      \}", READER, re.S
    )
    assert block, "reader reduced-motion block missing"
    body = block.group(1)
    assert ".sidebar" in body
    assert ".prose" in body
    assert "animation: none;" in body


def test_reader_loading_state_is_static():
    """Loading marks are not live data; they must not pulse."""
    assert "loadPulse" not in READER
    assert "animation: none" not in READER.split(".loading-dot", 1)[1][:400]
    assert 'loading.setAttribute("role", "status")' in READER


def test_matrix_headers_are_scoped():
    for page in ("education.html", "projects.html"):
        source = (ROOT / "templates" / "pages" / page).read_text()
        for header in re.findall(r"<th>(.*?)</th>", source):
            raise AssertionError(f"unscoped matrix header in {page}: {header}")


def test_mobile_primary_targets_reach_44px():
    mobile = STYLE[STYLE.index("@media (max-width: 640px)", STYLE.index("@media (max-width: 900px)")) :]
    assert re.search(r"\.nav-tab \{[^}]*min-height: 44px", mobile, re.S)
    assert re.search(r"\.realm-pill \{[^}]*min-height: 44px", mobile, re.S)
    assert re.search(r"\.task-check \{[^}]*width: 44px", mobile, re.S)
    assert re.search(r"\.header-btn \{[^}]*width: 44px", READER, re.S)


def test_metrics_heading_scale_steps_above_body():
    body = re.search(r"\.ops-table \{[^}]*font-size: (\d+)px", STYLE)
    h4 = re.search(r"\.metrics-section-heading h4 \{[^}]*font-size: (\d+)px", STYLE)
    assert body and h4
    assert int(h4.group(1)) / int(body.group(1)) >= 1.25


def test_data_hues_map_onto_the_verified_palette():
    """Legacy data colors must not bypass the contrast-checked palette."""
    palette = set(dashboard.SAFE_HUES.values())
    for legacy, safe in dashboard.SAFE_HUE_MAP.items():
        assert safe in palette, f"{legacy} maps to unverified {safe}"
    assert dashboard.safe_hue("#D97757") == dashboard.SAFE_HUES["vermilion"]
    assert dashboard.safe_hue("#888") == dashboard.SAFE_HUES["ink-muted"]
    assert dashboard.safe_hue("not-a-color") == dashboard.SAFE_HUES["ink-muted"]
    # app.py and tokens.css stay in sync.
    assert dashboard.SAFE_HUES["green"] == _token("green")
    assert dashboard.SAFE_HUES["blue"] == _token("blue")
    assert dashboard.SAFE_HUES["purple"] == _token("purple")
    assert dashboard.SAFE_HUES["red"] == _token("red")
    assert dashboard.SAFE_HUES["yellow"] == _token("yellow")
    assert dashboard.SAFE_HUES["vermilion"] == _token("vermilion")
    assert dashboard.SAFE_HUES["teal"] == _token("teal")


def test_printable_sheet_leading_and_fold_insets():
    sheet = (ROOT / "templates" / "interview_sheet.html").read_text()
    assert "line-height: 1.4" in sheet
    assert "line-height: 1.3" not in sheet
    tasks = (ROOT / "templates" / "pages" / "tasks.html").read_text()
    assert "padding-left: 20px;" in tasks


def test_agents_tab_renders_roster_and_a_contained_scan_table():
    assert '("agents", "Agents")' in INDEX
    assert 'include "pages/agents.html"' in INDEX
    page = (ROOT / "templates" / "pages" / "agents.html").read_text()
    assert 'id="page-agents"' in page
    assert 'aria-labelledby="tab-agents"' in page
    assert "agent_events[agent.slug]" in page
    assert "agent_scan.jobs" in page
    assert "No memory recorded" in page
    assert "No Scout scan yet" in page
    assert 'class="ops-table-scroll"' in page
    assert 'class="ops-table agents-scan-table"' in page
    assert ".agents-scan-table" in STYLE
    block = re.search(r"\.agents-scan-table \{[^}]*\}", STYLE)
    assert block and "min-width" in block.group(0)


def test_every_data_supplied_color_is_covered_by_the_safe_map():
    """Books and education YAML colors must all resolve to a verified hue."""
    yaml_files = [
        ROOT.parent / "Books" / "books-data.yml",
        ROOT.parent / "College Planning" / "education-data.yml",
    ]
    known = set(dashboard.SAFE_HUE_MAP) | {v.lower() for v in dashboard.SAFE_HUES.values()}
    for path in yaml_files:
        for raw in re.findall(r'color:\s*"(#[0-9a-fA-F]{3,6})"', path.read_text()):
            assert raw.lower() in known, f"{path.name} color {raw} bypasses SAFE_HUE_MAP"
