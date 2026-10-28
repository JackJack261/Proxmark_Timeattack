"""Title screen shown when the game launches.

Full-screen, centered "PROXMARK TIME ATTACK" banner in orange with a slow-
blinking "Press Enter to Start" prompt. The fancy path (alternate screen
buffer + blink) runs only on a real terminal; on a non-TTY it degrades to a
plain print + wait so tests and piped input never block or emit escape codes.
"""
import shutil
import sys

# ANSI escapes
ORANGE = "\033[38;5;208m"      # 256-colour orange
BOLD = "\033[1m"
RESET = "\033[0m"
ALT_SCREEN_ON = "\033[?1049h"  # switch to alternate screen buffer
ALT_SCREEN_OFF = "\033[?1049l"  # restore the normal screen
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
CLEAR = "\033[2J\033[H"

PROMPT = "Press Enter to Start"
BLINK_INTERVAL = 0.6  # seconds per on/off phase


def build_title_lines() -> list[str]:
    """The framed, spaced title banner as a list of equal-width lines."""
    title1 = "P R O X M A R K"
    title2 = "T I M E   A T T A C K"
    inner = max(len(title1), len(title2)) + 8
    top = "╔" + "═" * inner + "╗"
    bottom = "╚" + "═" * inner + "╝"
    blank = "║" + " " * inner + "║"
    line1 = "║" + title1.center(inner) + "║"
    line2 = "║" + title2.center(inner) + "║"
    return [top, blank, line1, line2, blank, bottom]


def _move(row: int, col: int) -> str:
    """ANSI cursor move to a 1-based (row, col)."""
    return f"\033[{row};{col}H"


def _layout(cols: int, rows: int):
    """Compute 1-based positions for the title block and the prompt."""
    lines = build_title_lines()
    block_w = len(lines[0])
    block_h = len(lines)
    gap = 2
    total_h = block_h + gap + 1  # block + gap + prompt
    top_row = max(0, (rows - total_h) // 2) + 1
    left_col = max(0, (cols - block_w) // 2) + 1
    prompt_row = top_row + block_h + gap
    prompt_col = max(0, (cols - len(PROMPT)) // 2) + 1
    return lines, top_row, left_col, prompt_row, prompt_col


def _blink_wait(stdout, stdin, prompt_row, prompt_col, interval) -> None:
    """Blink the prompt until the player presses Enter.

    Uses select() so the prompt keeps toggling while we wait for input,
    without raw-mode fiddling. Falls back to a plain blocking read where
    select() on stdin is not supported (e.g. Windows consoles).
    """
    import select

    visible = True
    while True:
        stdout.write(_move(prompt_row, prompt_col))
        if visible:
            stdout.write(ORANGE + BOLD + PROMPT + RESET)
        else:
            stdout.write(" " * len(PROMPT))
        stdout.write(_move(prompt_row, prompt_col))
        stdout.flush()
        try:
            ready, _, _ = select.select([stdin], [], [], interval)
        except (OSError, ValueError):
            stdin.readline()  # select unsupported here: just wait for Enter
            return
        if ready:
            stdin.readline()
            return
        visible = not visible


def show_title_screen(*, stdout=None, stdin=None, input_fn=input, interval=BLINK_INTERVAL) -> None:
    """Show the title screen and return once the player presses Enter.

    On a TTY: takes over the full screen (alternate buffer), draws the
    centered orange banner, and slow-blinks the prompt until Enter. On a
    non-TTY: prints the banner once and waits via ``input_fn`` (no escape
    codes, no blink), so it is safe under test capture and piped input.
    """
    stdout = stdout or sys.stdout
    stdin = stdin or sys.stdin

    lines = build_title_lines()

    if not stdout.isatty():
        for line in lines:
            stdout.write(line + "\n")
        stdout.write("\n" + PROMPT + "\n")
        stdout.flush()
        input_fn()
        return

    cols, rows = shutil.get_terminal_size(fallback=(80, 24))
    lines, top_row, left_col, prompt_row, prompt_col = _layout(cols, rows)
    try:
        stdout.write(ALT_SCREEN_ON + HIDE_CURSOR + CLEAR)
        for i, line in enumerate(lines):
            stdout.write(_move(top_row + i, left_col) + ORANGE + BOLD + line + RESET)
        stdout.flush()
        _blink_wait(stdout, stdin, prompt_row, prompt_col, interval)
    finally:
        stdout.write(SHOW_CURSOR + ALT_SCREEN_OFF)
        stdout.flush()
