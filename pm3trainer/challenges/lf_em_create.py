"""Challenge: clone an EM410x credential with a given ID onto a T5577."""
from __future__ import annotations

import random
from typing import Optional

from pm3trainer.answers import norm_hex
from pm3trainer.cards import CardKind
from pm3trainer.challenges.base import Challenge, Mode
from pm3trainer.parsers import parse_em410x

READ_COMMAND = "lf search"
CLONE_TEMPLATE = "lf em 410x clone --id {id}"


class LfEmCreate(Challenge):
    name = "LF EM410x create"
    mode = Mode.CREATE
    required_card = CardKind.T5577
    present_prompt = "Place a blank T5577 on the reader."

    def __init__(self, rng: random.Random):
        self.em_id = f"{rng.getrandbits(40):010x}"
        self.task_prompt = f"Write the EM410x ID {self.em_id} onto the T5577."
        self.hints = [
            "EM410x is a low-frequency (lf) tag; look under 'lf em 410x' for a clone command.",
            "The clone command takes the EM410x ID as an argument.",
            CLONE_TEMPLATE.format(id="<ID>"),
        ]
        self.solution = CLONE_TEMPLATE.format(id=self.em_id)

    def check(self, session, player_input: Optional[str]) -> bool:
        found = parse_em410x(session.run(READ_COMMAND))
        return found is not None and norm_hex(found) == norm_hex(self.em_id)
