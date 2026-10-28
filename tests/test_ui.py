import io

from pm3trainer import ui


def test_build_title_lines_equal_width_and_hold_title():
    lines = ui.build_title_lines()
    widths = {len(line) for line in lines}
    assert len(widths) == 1  # every line is the same width (aligned frame)
    joined = "\n".join(lines)
    assert "P R O X M A R K" in joined
    assert "T I M E   A T T A C K" in joined


def test_layout_centers_within_terminal():
    lines, top_row, left_col, prompt_row, prompt_col = ui._layout(80, 24)
    assert top_row >= 1 and left_col >= 1
    assert prompt_col >= 1
    # prompt sits below the whole title block
    assert prompt_row == top_row + len(lines) + 2


def test_layout_survives_tiny_terminal():
    # Smaller than the banner: positions clamp to >= 1, no negative moves.
    _, top_row, left_col, prompt_row, prompt_col = ui._layout(10, 3)
    assert top_row >= 1 and left_col >= 1
    assert prompt_row >= 1 and prompt_col >= 1


def test_non_tty_prints_banner_and_waits_without_escape_codes():
    out = io.StringIO()  # StringIO.isatty() is False -> simple path
    calls = []
    ui.show_title_screen(stdout=out, stdin=io.StringIO(), input_fn=lambda: calls.append(True) or "")
    text = out.getvalue()
    assert "P R O X M A R K" in text
    assert ui.PROMPT in text
    assert "\033" not in text  # no ANSI escapes on a non-TTY
    assert calls == [True]  # waited exactly once via the injected input
