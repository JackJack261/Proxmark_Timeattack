"""Entry point: wires the session, challenges, game loop and high scores together."""
import argparse
import random
import sys
import time

from pm3trainer.game import GameAborted, build_challenges, run_game
from pm3trainer.scoring import (
    HINT_PENALTY,
    PASS_PENALTY,
    HighScores,
    total_seconds,
)
from pm3trainer.session import Pm3Disconnected, Pm3Session

SCORES_PATH = "scores.json"

INTRO = f"""\
=== Proxmark3 Time Attack ===
Complete every challenge as fast as you can. The clock runs the whole time.
Type 'hint' for a nudge (+{HINT_PENALTY:.0f}s) or 'pass' to skip a challenge (+{PASS_PENALTY:.0f}s).
"""


def format_time(seconds: float) -> str:
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes):d}:{secs:04.1f}"


def print_results(results, output_fn=print) -> None:
    output_fn("")
    output_fn(f"{'Challenge':<28}{'Time':>9}{'Hints':>7}  Status")
    for r in results:
        status = "SKIPPED" if r.skipped else ""
        output_fn(f"{r.name:<28}{format_time(r.total):>9}{r.hints_used:>7}  {status}".rstrip())
    output_fn(f"{'TOTAL':<28}{format_time(total_seconds(results)):>9}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="pm3trainer", description="Proxmark3 time-attack trainer")
    parser.add_argument("--port", default=None, help="serial port, e.g. /dev/ttyACM0")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    session = Pm3Session(port=args.port)
    try:
        try:
            session.start()
        except Pm3Disconnected:
            print(
                "Sorry, couldn't connect to the Proxmark3. Check that it is plugged in, "
                "the pm3 client is installed, and (if needed) pass --port /dev/ttyACMx."
            )
            return 1

        challenges = build_challenges(random.Random())
        print(INTRO)
        try:
            results = run_game(
                session,
                challenges,
                input_fn=input,
                output_fn=print,
                clock=time.monotonic,
            )
        except GameAborted as aborted:
            print("Game ended early.")
            if aborted.results:
                print_results(aborted.results)
            return 1

        print_results(results)
        scores = HighScores(SCORES_PATH)
        if scores.record(total_seconds(results)):
            print("New best time!")
        elif scores.best() is None:
            print("(Could not save your best time; check that the directory is writable.)")
        else:
            print(f"Best time to beat: {format_time(scores.best())}")
        return 0
    except (KeyboardInterrupt, EOFError):
        print("\nQuit. Thanks for playing!")
        return 130
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
