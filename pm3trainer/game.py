"""Game loop: presents each challenge, times the player, and records results."""
from __future__ import annotations

import random
from typing import Callable

from pm3trainer import guard
from pm3trainer.cards import verify_card
from pm3trainer.challenges.base import Challenge, Mode
from pm3trainer.challenges.hf_iclass_create import HfIclassCreate
from pm3trainer.challenges.hf_mf_create import HfMfCreate
from pm3trainer.challenges.hf_mf_read import HfMfRead
from pm3trainer.challenges.lf_em_create import LfEmCreate
from pm3trainer.challenges.lf_em_read import LfEmRead
from pm3trainer.challenges.lf_hid_create import LfHidCreate
from pm3trainer.scoring import ChallengeResult
from pm3trainer.session import Pm3Disconnected, Pm3Timeout

PROMPT = "> "
TIMEOUT_MESSAGE = "The Proxmark3 timed out. Try again."
DISCONNECT_MESSAGE = (
    "Proxmark3 disconnected. Reconnect the device and restart the game."
)

# First word of a line that means "this is a pm3 command to run", not a READ
# answer. Answers are bare hex IDs/UIDs, which never start with one of these.
COMMAND_ROOTS = frozenset({
    "lf", "hf", "data", "hw", "mem", "trace", "reveng", "analyse",
    "script", "pref", "prefs", "emv", "smart", "nfc", "piv", "wiegand", "help",
})


def _looks_like_command(line: str) -> bool:
    parts = line.split()
    return bool(parts) and parts[0].lower() in COMMAND_ROOTS


def _is_help(line: str) -> bool:
    tokens = line.lower().split()
    return (tokens[:1] == ["help"]) or "-h" in tokens or "--help" in tokens


def _run_command(session, line, card_state, output_fn) -> bool:
    """Guard, run a command on the device, and show its output.

    Returns False if the guard blocked it (nothing was sent)."""
    verdict = guard.check(line, card_state)
    if not verdict.allowed:
        output_fn(verdict.reason)
        return False
    output = session.run(line)
    if output.strip():
        output_fn(output)
    return True


class GameAborted(Exception):
    """The game cannot continue (device disconnected).

    ``results`` holds the challenges completed before the abort.
    """

    def __init__(self, results: list[ChallengeResult]):
        super().__init__("game aborted: Proxmark3 disconnected")
        self.results = results


def build_challenges(rng: random.Random) -> list[Challenge]:
    """The fixed, ordered set of six challenges."""
    return [
        LfHidCreate(rng),
        LfEmCreate(rng),
        HfMfCreate(rng),
        HfIclassCreate(rng),
        LfEmRead(rng),
        HfMfRead(rng),
    ]


def _present_card(session, challenge, input_fn, output_fn):
    """Prompt until the right card is on the reader; return its CardState.

    Runs before the clock starts, so card swaps are not charged to the player.
    """
    output_fn(challenge.present_prompt)
    while True:
        input_fn("Press Enter when the card is on the reader... ")
        try:
            card = verify_card(session, challenge.required_card)
        except Pm3Timeout:
            output_fn(TIMEOUT_MESSAGE)
            continue
        if card.ok:
            output_fn(card.detail)
            return card.state
        output_fn(card.detail)
        output_fn(challenge.present_prompt)


def _setup(session, challenge, input_fn, output_fn):
    """Run the READ challenge's setup, retrying after a timeout."""
    while True:
        try:
            challenge.setup(session)
            return
        except Pm3Timeout:
            output_fn(TIMEOUT_MESSAGE)
            input_fn("Press Enter to retry... ")


def _play(session, challenge, *, input_fn, output_fn, clock) -> ChallengeResult:
    card_state = _present_card(session, challenge, input_fn, output_fn)

    # READ challenges write their ground truth before the clock starts, so the
    # player is never timed for the game's own silent write.
    if challenge.mode is Mode.READ:
        _setup(session, challenge, input_fn, output_fn)
    start = clock()
    output_fn(challenge.task_prompt)

    hints_used = 0
    skipped = False
    while True:
        line = input_fn(PROMPT).strip()
        word = line.lower()

        # Reserved words are handled before the guard and never reach the device.
        if word == "hint":
            if challenge.hints:
                index = min(hints_used, len(challenge.hints) - 1)
                output_fn(f"Hint: {challenge.hints[index]}")
                hints_used += 1
            continue
        if word == "pass":
            output_fn(f"Solution: {challenge.solution}")
            skipped = True
            break
        if not line:
            continue

        challenge.feedback = ""
        try:
            if challenge.mode is Mode.CREATE:
                # Everything typed is a command: run it, show output, then
                # check the card — except a help/usage query, which just shows.
                if not _run_command(session, line, card_state, output_fn):
                    continue
                if _is_help(line):
                    continue
                passed = challenge.check(session, None)
            elif _looks_like_command(line):
                # READ: run the read command and show its output; the player
                # reads the value off it and types it back as the answer next.
                _run_command(session, line, card_state, output_fn)
                continue
            else:
                passed = challenge.check(session, line)
        except Pm3Timeout:
            output_fn(TIMEOUT_MESSAGE)
            continue

        if passed:
            output_fn("Correct!")
            break
        output_fn("Not quite. Try again.")
        if challenge.feedback:
            output_fn(challenge.feedback)

    elapsed = clock() - start
    return ChallengeResult(challenge.name, elapsed, hints_used, skipped)


def run_game(
    session,
    challenges: list[Challenge],
    *,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    clock: Callable[[], float],
) -> list[ChallengeResult]:
    """Play every challenge in order and return the per-challenge results.

    Raises GameAborted if the device disconnects. Recording the final total is
    left to the caller.
    """
    results: list[ChallengeResult] = []
    try:
        for challenge in challenges:
            results.append(
                _play(
                    session,
                    challenge,
                    input_fn=input_fn,
                    output_fn=output_fn,
                    clock=clock,
                )
            )
    except Pm3Disconnected:
        output_fn(DISCONNECT_MESSAGE)
        raise GameAborted(results)
    return results
