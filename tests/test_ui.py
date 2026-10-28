import io

from pm3trainer import ui


def test_build_title_lines_equal_width_and_big():
    lines = ui.build_title_lines()
    widths = {len(line) for line in lines}
    assert len(widths) == 1  # every line is the same width (clean centering)
    # Two words of GLYPH_H block rows plus one gap row.
    assert len(lines) == ui.GLYPH_H * 2 + 1
    assert "█" in "\n".join(lines)  # rendered as solid blocks


def test_layout_centers_within_terminal():
    lines, top_row, left_col, prompt_row, prompt_col = ui._layout(100, 40)
    assert top_row >= 1 and left_col >= 1 and prompt_col >= 1
    assert prompt_row == top_row + len(lines) + 2  # prompt below the block


def test_layout_survives_tiny_terminal():
    _, top_row, left_col, prompt_row, prompt_col = ui._layout(10, 3)
    assert top_row >= 1 and left_col >= 1
    assert prompt_row >= 1 and prompt_col >= 1


def test_non_tty_prints_banner_and_waits_without_escape_codes():
    out = io.StringIO()  # StringIO.isatty() is False -> simple path
    calls = []
    ui.show_title_screen(stdout=out, stdin=io.StringIO(), input_fn=lambda: calls.append(True) or "")
    text = out.getvalue()
    assert "█" in text  # block banner rendered
    assert ui.PROMPT in text
    assert "\033" not in text  # no ANSI escapes on a non-TTY
    assert calls == [True]  # waited exactly once via the injected input


def test_fullscreen_noop_on_non_tty():
    out = io.StringIO()
    with ui.fullscreen(stdout=out):
        out.write("game")
    text = out.getvalue()
    assert ui.ALT_SCREEN_ON not in text and ui.ALT_SCREEN_OFF not in text
    assert text == "game"


def test_wait_for_enter_noop_on_non_tty():
    out = io.StringIO()
    calls = []
    ui.wait_for_enter(stdout=out, input_fn=lambda: calls.append(True) or "")
    assert out.getvalue() == ""  # nothing drawn, nothing read
    assert calls == []
