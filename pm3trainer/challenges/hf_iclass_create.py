"""Challenge: write given data into a block of a writable iClass card."""
from __future__ import annotations

import random
from typing import Optional

from pm3trainer.answers import norm_hex
from pm3trainer.cards import CardKind
from pm3trainer.challenges.base import Challenge, Mode
from pm3trainer.parsers import parse_iclass_block

# NOTE: iClass command syntax is best-effort (no device to verify against);
# Task 15 reconciles these strings. Keep all command text in this block.
BLOCK = 7
READ_TEMPLATE = "hf iclass rdbl --blk {block}"
WRITE_TEMPLATE = "hf iclass wrbl --blk {block} -d {data}"


class HfIclassCreate(Challenge):
    name = "HF iClass create"
    mode = Mode.CREATE
    required_card = CardKind.WRITABLE_ICLASS
    present_prompt = "Place a writable iClass card on the reader."

    def __init__(self, rng: random.Random):
        self.data = f"{rng.getrandbits(64):016x}"
        self.task_prompt = (
            f"Write the data {self.data} to block {BLOCK} of the writable iClass card."
        )
        self.hints = [
            "iClass is a high-frequency (hf) tag; look under 'hf iclass' for block read/write commands.",
            "You need a block-write command that takes the block number and the 8 bytes of data as arguments.",
            WRITE_TEMPLATE.format(block=BLOCK, data="<DATA>"),
        ]
        self.solution = WRITE_TEMPLATE.format(block=BLOCK, data=self.data)

    def check(self, session, player_input: Optional[str]) -> bool:
        output = session.run(READ_TEMPLATE.format(block=BLOCK))
        found = parse_iclass_block(output, BLOCK)
        if found is not None and norm_hex(found) == norm_hex(self.data):
            return True
        self.feedback = (
            f"Block {BLOCK} reads as {found.upper()}." if found
            else f"Block {BLOCK} could not be read from the card."
        )
        return False
