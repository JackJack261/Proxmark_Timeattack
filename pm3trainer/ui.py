"""Title screen and full-screen helpers for the launcher.

A large, centered "PROXMARK / TIME ATTACK" banner in orange block letters with
a slow-blinking "Press Enter to Start" prompt. The whole game runs inside the
terminal's alternate screen buffer (see ``fullscreen``) so it does not drop
back to the shell between the title and play; the shell is restored cleanly on
exit. The fancy path runs only on a real terminal; on a non-TTY everything
degrades to plain prints so tests and piped input never block or emit escapes.
"""
import contextlib
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
EXIT_PROMPT = "Press Enter to return to your shell..."
BLINK_INTERVAL = 0.6  # seconds per on/off phase

GLYPH_H = 5
_GAP = " "
# 5-row block glyphs (authored with '#', rendered as solid blocks).
_FONT = {
    "P": ["#### ", "#   #", "#### ", "#    ", "#    "],
    "R": ["#### ", "#   #", "#### ", "#  # ", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", " ### "],
    "X": ["#   #", " # # ", "  #  ", " # # ", "#   #"],
    "M": ["#   #", "## ##", "# # #", "#   #", "#   #"],
    "A": [" ### ", "#   #", "#####", "#   #", "#   #"],
    "K": ["#   #", "#  # ", "###  ", "#  # ", "#   #"],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  "],
    "I": ["#####", "  #  ", "  #  ", "  #  ", "#####"],
    "E": ["#####", "#    ", "#### ", "#    ", "#####"],
    "C": [" ####", "#    ", "#    ", "#    ", " ####"],
    " ": ["     ", "     ", "     ", "     ", "     "],
}


def _render_word(word: str) -> list[str]:
    """Render a word as GLYPH_H rows of block letters."""
    rows = ["" for _ in range(GLYPH_H)]
    chars = list(word.upper())
    for i, ch in enumerate(chars):
        glyph = _FONT.get(ch, _FONT[" "])
        for r in range(GLYPH_H):
            rows[r] += glyph[r]
            if i != len(chars) - 1:
                rows[r] += _GAP
    return [row.replace("#", "█") for row in rows]


def build_title_lines() -> list[str]:
    """The big two-word banner as a list of equal-width lines."""
    word1 = _render_word("PROXMARK")
    word2 = _render_word("TIME ATTACK")
    width = max(len(word1[0]), len(word2[0]))
    lines = [row.center(width) for row in word1]
    lines.append(" " * width)
    lines.extend(row.center(width) for row in word2)
    return lines


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


@contextlib.contextmanager
def fullscreen(stdout=None):
    """Hold the terminal's alternate screen buffer for the whole game.

    Entering clears to a blank full screen; leaving restores the shell and the
    cursor. On a non-TTY it is a no-op so tests and pipes are unaffected.
    """
    stdout = stdout or sys.stdout
    if not stdout.isatty():
        yield
        return
    stdout.write(ALT_SCREEN_ON + CLEAR)
    stdout.flush()
    try:
        yield
    finally:
        stdout.write(SHOW_CURSOR + ALT_SCREEN_OFF)
        stdout.flush()


@contextlib.contextmanager
def enter_key_fix(stdin=None):
    """Make Enter terminate canonical input lines for the game's duration.

    Some terminals deliver a bare carriage return with ICRNL off, so ``input()``
    never completes (Enter echoes "^M" and reads hang). Turn ICRNL on (plus
    canonical mode and echo) and restore the original settings on exit. No-op
    where termios is unavailable (e.g. Windows) or stdin is not a tty.
    """
    stdin = stdin or sys.stdin
    try:
        import termios
        fd = stdin.fileno()
        old = termios.tcgetattr(fd)
    except Exception:
        yield
        return
    new = termios.tcgetattr(fd)
    new[0] |= termios.ICRNL                    # iflag: map CR -> NL on input
    new[3] |= termios.ICANON | termios.ECHO    # lflag: line mode + echo
    try:
        termios.tcsetattr(fd, termios.TCSANOW, new)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def wait_for_enter(message: str = EXIT_PROMPT, *, stdout=None, input_fn=input) -> None:
    """On a TTY, show a message and wait for Enter (so the last screen stays
    readable before the alternate buffer is torn down). No-op on a non-TTY."""
    stdout = stdout or sys.stdout
    if not stdout.isatty():
        return
    stdout.write("\n" + ORANGE + message + RESET + "\n" + SHOW_CURSOR)
    stdout.flush()
    try:
        input_fn()
    except (EOFError, KeyboardInterrupt):
        pass


def _draw_prompt(stdout, prompt_row, prompt_col, visible) -> None:
    stdout.write(_move(prompt_row, prompt_col))
    stdout.write((ORANGE + BOLD + PROMPT + RESET) if visible else " " * len(PROMPT))
    stdout.write(_move(prompt_row, prompt_col))
    stdout.flush()


def _blink_wait(stdout, stdin, prompt_row, prompt_col, interval) -> None:
    """Blink the prompt until the player presses Enter.

    Reads the key directly in cbreak mode and treats CR or LF as Enter, so it
    works even on terminals that deliver a bare carriage return and never
    complete a canonical input line (the symptom: Enter echoes "^M" and
    line-buffered reads hang). Falls back to a blocking readline where termios
    is unavailable (e.g. Windows).
    """
    import os
    import select

    try:
        import termios
        fd = stdin.fileno()
        old = termios.tcgetattr(fd)
    except Exception:
        _blink_wait_readline(stdout, stdin, prompt_row, prompt_col, interval)
        return

    new = termios.tcgetattr(fd)
    new[3] &= ~(termios.ICANON | termios.ECHO)  # raw-ish: per-key, no echo
    new[6][termios.VMIN] = 1
    new[6][termios.VTIME] = 0
    try:
        termios.tcsetattr(fd, termios.TCSANOW, new)
        visible = True
        while True:
            _draw_prompt(stdout, prompt_row, prompt_col, visible)
            ready, _, _ = select.select([fd], [], [], interval)
            if ready:
                ch = os.read(fd, 1)
                if ch in (b"\r", b"\n"):
                    while select.select([fd], [], [], 0)[0]:  # drain a paired CR/LF
                        os.read(fd, 1)
                    return
            else:
                visible = not visible
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _blink_wait_readline(stdout, stdin, prompt_row, prompt_col, interval) -> None:
    """Fallback for platforms without termios: blocking read on a thread."""
    import threading

    done = threading.Event()

    def _await_enter():
        try:
            stdin.readline()
        except Exception:
            pass
        finally:
            done.set()

    threading.Thread(target=_await_enter, daemon=True).start()
    visible = True
    while True:
        _draw_prompt(stdout, prompt_row, prompt_col, visible)
        if done.wait(interval):
            return
        visible = not visible


def show_title_screen(*, stdout=None, stdin=None, input_fn=input, interval=BLINK_INTERVAL) -> None:
    """Draw the centered banner and return once the player presses Enter.

    Assumes it is already inside ``fullscreen`` on a TTY: it clears, draws the
    orange banner, slow-blinks the prompt, then clears again so the game starts
    on a fresh screen. On a non-TTY it prints the banner once and waits via
    ``input_fn`` (no escapes, no blink).
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
    stdout.write(HIDE_CURSOR + CLEAR)
    for i, line in enumerate(lines):
        stdout.write(_move(top_row + i, left_col) + ORANGE + BOLD + line + RESET)
    stdout.flush()
    _blink_wait(stdout, stdin, prompt_row, prompt_col, interval)
    stdout.write(SHOW_CURSOR + CLEAR)  # fresh screen for the game, cursor back
    stdout.flush()
