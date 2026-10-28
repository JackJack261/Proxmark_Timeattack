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

    start = clock()
    if challenge.mode is Mode.READ:
        _setup(session, challenge, input_fn, output_fn)
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

        try:
            if challenge.mode is Mode.CREATE:
                verdict = guard.check(line, card_state)
                if not verdict.allowed:
                    output_fn(verdict.reason)
                    continue
                session.run(line)
                passed = challenge.check(session, None)
            else:
                passed = challenge.check(session, line)
        except Pm3Timeout:
            output_fn(TIMEOUT_MESSAGE)
            continue

        if passed:
            output_fn("Correct!")
            break
        output_fn("Not quite. Try again.")

    elapsed = clock() - start
    return ChallengeResult(challenge.name, elapsed, hints_used, skipped)


def run_game(
    session,
    challenges: list[Challenge],
    *,
    input_fn: Callable[[str], str],
    output_fn: Callable[[str], None],
    clock: Callable[[], float],
    scores,
) -> list[ChallengeResult]:
    """Play every challenge in order and return the per-challenge results.

    Raises GameAborted if the device disconnects. ``scores`` is accepted for the
    entry point's convenience; recording the final total is left to the caller.
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
