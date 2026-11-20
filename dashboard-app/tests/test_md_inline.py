"""Task text is file content: markdown renders, everything else is escaped."""

from core.today import md_inline


def test_code_and_bold_render_and_links_keep_their_text():
    html = str(md_inline("**Check**: `gh repo view` in [notes](docs/n.md)"))
    assert html == "<strong>Check</strong>: <code>gh repo view</code> in notes"


def test_html_in_task_text_is_escaped():
    html = str(md_inline("<img src=x onerror=alert(1)> `<b>`"))
    assert "<img" not in html and "<b>" not in html
    assert "<code>&lt;b&gt;</code>" in html


def test_globs_inside_code_do_not_open_bold():
    html = str(md_inline("`a/**` and `b/**`"))
    assert html == "<code>a/**</code> and <code>b/**</code>"
