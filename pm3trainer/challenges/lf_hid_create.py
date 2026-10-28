"""Challenge: clone an HID Prox credential with a given FC/CN onto a T5577."""
from __future__ import annotations

import random
from typing import Optional

from pm3trainer.cards import CardKind
from pm3trainer.challenges.base import Challenge, Mode
from pm3trainer.parsers import parse_hid

READ_COMMAND = "lf hid reader"


class LfHidCreate(Challenge):
    name = "LF HID create"
    mode = Mode.CREATE
    required_card = CardKind.T5577
    present_prompt = "Place a blank T5577 on the reader."

    def __init__(self, rng: random.Random):
        self.fc = rng.randint(0, 255)
        self.cn = rng.randint(0, 65535)
        self.task_prompt = (
            f"Write an HID Prox credential with FC {self.fc} and CN {self.cn} "
            "onto the T5577."
        )
        self.hints = [
            "HID Prox is a low-frequency (lf) tag; look for an 'lf hid' command that clones.",
            "The clone command takes the facility code and card number as arguments.",
            "lf hid clone -w H10301 --fc <FC> --cn <CN>",
        ]
        self.solution = f"lf hid clone -w H10301 --fc {self.fc} --cn {self.cn}"

    def check(self, session, player_input: Optional[str]) -> bool:
        result = parse_hid(session.run(READ_COMMAND))
        return result is not None and result.fc == self.fc and result.cn == self.cn
