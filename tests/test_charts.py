from io import StringIO

import pytest
from rich.console import Console
from rich.text import Text

from dv.core.stats import ScatterGrid, bins_from_values
from dv.render import theme
from dv.render.charts import _bar_text, render_bar, render_scatter, render_sparkline
from dv.render.histogram import render_histogram
from dv.render.theme import ASCII, UNICODE, set_charset


@pytest.fixture(params=[ASCII, UNICODE], ids=["ascii", "unicode"])
def charset(request):
    """Run each rendering test under both charsets."""
    set_charset(request.param is UNICODE)
    yield request.param
    set_charset(False)


def _capture(fn, *args, **kwargs) -> str:
    """Render into a fixed-width buffer instead of the terminal."""
    buf = StringIO()
    original = theme.console
    theme.console = Console(file=buf, highlight=False, markup=False, width=80)
    try:
        import dv.render.charts as charts_mod
        import dv.render.histogram as hist_mod
        orig_c, orig_h = charts_mod.console, hist_mod.console
        charts_mod.console = hist_mod.console = theme.console
        try:
            fn(*args, **kwargs)
        finally:
            charts_mod.console, hist_mod.console = orig_c, orig_h
    finally:
        theme.console = original
    return buf.getvalue()


def test_bar_full(charset):
    t = _bar_text(10.0, 10.0, 10)
    assert isinstance(t, Text)
    assert charset.bar * 10 in t.plain


def test_bar_half(charset):
    assert charset.bar in _bar_text(5.0, 10.0, 10).plain


def test_bar_zero(charset):
    assert _bar_text(0.0, 10.0, 10).plain.strip() == ""


def test_bar_no_max_is_blank(charset):
    assert _bar_text(5.0, 0.0, 10).plain.strip() == ""


def test_render_bar_output(charset):
    output = _capture(render_bar, [("a", 5), ("b", 10)], title="test")
    assert "a" in output
    assert "b" in output
    assert charset.bar in output


def test_render_sparkline(charset):
    output = _capture(render_sparkline, [1.0, 2.0, 3.0, 2.0, 1.0], title="t")
    assert any(c in output for c in charset.spark)


def test_render_histogram_bins(charset):
    output = _capture(render_histogram, bins_from_values(list(range(100)), bins=5))
    assert charset.bar in output


def test_histogram_empty():
    assert "No data" in _capture(render_histogram, [])


def test_histogram_constant_column():
    output = _capture(render_histogram, bins_from_values([7.0, 7.0, 7.0]))
    assert "All values are 7" in output


def _grid(pts):
    """A ScatterGrid over unweighted points, as core.stats would produce."""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return ScatterGrid(points=[(x, y, 1) for x, y in pts],
                       x_min=min(xs), x_max=max(xs), y_min=min(ys), y_max=max(ys))


def test_render_scatter_basic(charset):
    pts = [(float(x), float(x * 2)) for x in range(1, 11)]
    output = _capture(render_scatter, _grid(pts), x_label="hours", y_label="score", height=10)
    assert charset.dot in output
    assert "hours" in output
    assert "score" in output


def test_render_scatter_empty():
    assert "No data" in _capture(render_scatter, None)


def test_render_scatter_axes(charset):
    pts = [(0.0, 0.0), (10.0, 100.0)]
    output = _capture(render_scatter, _grid(pts), x_label="x", y_label="y", height=10)
    assert "0" in output
    assert "10" in output


def test_ascii_output_has_no_unicode_glyphs():
    """The default charset must stay safe for plain terminals and pipes."""
    set_charset(False)
    output = _capture(render_bar, [("a", 5), ("b", 10)], title="t")
    output += _capture(render_sparkline, [1.0, 5.0, 3.0], title="t")
    output += _capture(render_histogram, bins_from_values(list(range(50)), bins=4))
    assert output.isascii(), [c for c in output if not c.isascii()]
