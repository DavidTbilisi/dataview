from io import StringIO
from rich.console import Console
from rich.text import Text

from dv.render.charts import render_bar, render_sparkline, render_scatter, _bar_unicode
from dv.render.histogram import render_histogram


def _capture(fn, *args, **kwargs) -> str:
    buf = StringIO()
    c = Console(file=buf, highlight=False, markup=False, width=80)
    import dv.render.charts as charts_mod
    import dv.render.histogram as hist_mod
    orig_c = charts_mod.console
    orig_h = hist_mod.console
    charts_mod.console = c
    hist_mod.console = c
    try:
        fn(*args, **kwargs)
    finally:
        charts_mod.console = orig_c
        hist_mod.console = orig_h
    return buf.getvalue()


def test_bar_unicode_full():
    t = _bar_unicode(10.0, 10.0, 10)
    assert isinstance(t, Text)
    assert "█" * 10 in t.plain


def test_bar_unicode_half():
    t = _bar_unicode(5.0, 10.0, 10)
    plain = t.plain
    assert "█" in plain


def test_bar_unicode_zero():
    t = _bar_unicode(0.0, 10.0, 10)
    assert t.plain.strip() == ""


def test_render_bar_output():
    output = _capture(render_bar, [("a", 5), ("b", 10)], title="test")
    assert "a" in output
    assert "b" in output
    assert "█" in output


def test_render_sparkline_unicode():
    output = _capture(render_sparkline, [1.0, 2.0, 3.0, 2.0, 1.0], title="t")
    # should contain block characters
    assert any(c in output for c in "▁▂▃▄▅▆▇█")


def test_render_histogram_bins():
    output = _capture(render_histogram, list(range(100)), bins=5)
    assert "█" in output


def test_histogram_empty():
    output = _capture(render_histogram, [])
    assert "No data" in output


def test_render_scatter_basic():
    pts = [(float(x), float(x * 2)) for x in range(1, 11)]
    output = _capture(render_scatter, pts, x_label="hours", y_label="score", height=10)
    assert "◆" in output
    assert "hours" in output
    assert "score" in output


def test_render_scatter_empty():
    output = _capture(render_scatter, [])
    assert "No data" in output


def test_render_scatter_axes():
    pts = [(0.0, 0.0), (10.0, 100.0)]
    output = _capture(render_scatter, pts, x_label="x", y_label="y", height=10)
    assert "0" in output
    assert "10" in output
