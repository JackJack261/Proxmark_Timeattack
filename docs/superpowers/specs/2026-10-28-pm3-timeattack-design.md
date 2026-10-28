# Proxmark3 Time Attack Trainer — Design Spec

**Date:** 2026-10-28
**Status:** Approved design, pre-implementation

## Purpose

A terminal game that teaches people to use the Proxmark3 by having them
execute real commands on a connected device under a timer. The player is
given randomized challenges (e.g. "Make an LF HID card: FC 240, CN 2772"),
types the real `pm3` commands to complete them, and the game independently
verifies the result on the same hardware. It is timed, so the goal is to
complete all challenges as fast as possible.

**Audience:** People learning the Proxmark3 — enough familiarity to know the
tool exists, using the game to build speed and recall of real command syntax.

**Success looks like:** A player with a Proxmark3 and the right cards can run
one program, be walked through 6 challenges spanning LF/HF read and write
operations, and get a scored time at the end — with the game correctly
executing their commands on the device and verifying each result.

## Hardware & environment

- Runs on **Kali Linux**.
- **One Proxmark3** plugged in (typically `/dev/ttyACM0`).
- **Python 3 + `pexpect`** (`apt install python3-pexpect`, or pip).
- Official Proxmark3 client installed and on PATH as `pm3` (or
  `proxmark3 /dev/ttyACM0`).
- Rewritable cards required for write challenges:
  - **T5577** (LF, rewritable) — challenges 1, 2, 5
  - **Magic / gen Mifare Classic** (HF, rewritable UID) — challenges 3, 6
  - **Writable iClass** — challenge 4

## Core mechanic

The game is a wrapper/orchestrator around the real `pm3` client. The player
types real commands; the game runs them on the device and captures the text
output to verify results. Two challenge shapes share one opening:

**Shared opening (every challenge):**
1. Prompt the player to present a card (states whether LF or HF).
2. Read the card to verify the type is correct and that it is writable
   (T5577 / magic Mifare / writable iClass). Wrong card → tell the player and
   wait. This happens **before the clock starts**.

**① CREATE challenge** (player writes, game verifies):
- Clock starts; game shows the randomized target.
- Player types the write command → guard checks it → game runs it on the
  device → game reads the card back itself and compares to the target.

**② READ challenge** (game writes ground truth, player reads):
- Game silently writes randomized data to the presented card (its secret
  ground truth), then clock starts.
- Player runs the read/dump command and types the value back.
- Game compares the player's reported value to what it wrote.

Clock stops on pass. Wrong answer or failed verify → **unlimited retries,
clock keeps running** (time is the penalty). Fixed challenge order 1→6.

At any command/answer prompt the player can instead type one of two reserved
words:
- **`hint`** — reveals the next hint for this challenge (hints are an ordered
  list; the first is a nudge, the last is essentially the command with
  placeholders). Each hint adds a **+30s** penalty. No cap beyond the list.
- **`pass`** — gives up: reveals the challenge's solution, marks it skipped,
  adds a **+180s** penalty, and moves on to the next challenge.

`hint` and `pass` are matched case-insensitively on the trimmed input; no real
`pm3` command or hex answer collides with them.

## Challenge lineup

| # | Type | Challenge | Card | Player runs (example) | Verified by |
|---|------|-----------|------|------------------------|-------------|
| 1 | CREATE | LF HID Prox — random FC + CN | T5577 | `lf hid clone -w H10301 --fc <fc> --cn <cn>` | game reads `lf hid reader`, parse FC/CN |
| 2 | CREATE | LF EM410x — random 10-hex ID | T5577 | `lf em 410x clone --id <id>` | game reads `lf search` / `lf em 410x reader`, parse ID |
| 3 | CREATE | HF Mifare Classic — random UID | magic Mifare | `hf mf csetuid -u <uid>` | game reads `hf mf info` / `hf 14a info`, parse UID |
| 4 | CREATE | HF iClass — random data block | writable iClass | `hf iclass <write>` | game reads iClass block, compare data |
| 5 | READ | Game writes random EM410x ID → player identifies it | T5577 | `lf search` | player types ID; compare to ground truth |
| 6 | READ | Game writes random Mifare UID → player identifies it | magic Mifare | `hf search` / `hf mf info` | player types UID; compare to ground truth |

Randomized params are generated per run at challenge instantiation.

## Module layout

- **`pm3trainer.py`** — entry point. Parses optional args (e.g. device port),
  starts the session, runs the game, handles top-level errors and clean exit.
- **`pm3_session.py`** — owns the persistent pexpect session.
  - `start()` — spawn `pm3` (or `proxmark3 <port>`), wait for the
    `[usb] pm3 -->` prompt.
  - `run(cmd, timeout)` — send a command, read until the prompt returns,
    strip ANSI color codes, return the captured text.
  - `close()` — quit the client cleanly.
  - Detects prompt via regex; guards against timeouts and device-disconnect.
- **`guard.py`** — command safety check.
  - `check(cmd, card_state)` → allow, or block with a human-readable reason.
  - Single rule (see below).
- **`cards.py`** — card detection and verification helpers.
  - Detect LF vs HF and chip type via `lf search` / `hf search`.
  - Confirm writability (T5577 / magic Mifare / writable iClass).
  - Track each presented card's **password state** for the guard.
- **`challenges/`** — package with a base `Challenge` class and one subclass
  per challenge. Each subclass defines: required card type, randomized
  parameters, the player-facing prompt text, an optional `setup()` (READ
  challenges write ground truth here), and a `verify()` that reads the card
  and/or compares the player's answer.
  - Code-based challenge objects (not a config file) because each verifier
    needs custom output-parsing logic.
- **`game.py`** — the loop/orchestrator: intro, per-challenge flow, timing,
  scoring, results screen, high-score persistence.

## Command guard

Every command the player types in a CREATE challenge passes through
`guard.check()` before it is sent to the device.

**Rule (the only one):** Block an LF T55xx read that supplies a password
(`-p` / `--pwd`) **unless** the game has positively confirmed that the
presented card has a password set. Default-deny — if the game is not certain a
password is set, it refuses the password-read, prints the reason, leaves the
device untouched, and lets the player retry. This prevents the known footgun
of password-reading a passwordless T5577 and corrupting it.

The game knows password state because it controls challenge setup and
type-verification; `cards.py` records whether a password was set on the
current card. Unknown state is treated as "no password" (default-deny).

## Timing & scoring

- Monotonic clock per challenge. Card-present and type-verification happen
  before the clock starts, so hunting for a card is not timed.
- Clock starts when the task is revealed (CREATE) or after ground truth is
  written (READ); stops on pass.
- **Penalties** add to a challenge's time: `HINT_PENALTY = 30` seconds per
  hint used, `PASS_PENALTY = 180` seconds for a skip. A challenge's recorded
  time = elapsed clock + (hints_used × 30) + (180 if skipped).
- Total = sum of all six challenge times (including penalties).
- End screen: per-challenge times + total, with pass markers, hints used, and
  any skipped challenges called out.
- **`scores.json`** in the program directory stores the player's best total
  time; the end screen reports whether this run beat it.

## Read-challenge answer normalization

Player-typed answers are normalized before comparison: trim whitespace,
case-insensitive hex, ignore separators (spaces/colons). Exact rules per
challenge live in that challenge's `verify()`.

## Error handling

- **Client won't start / no device** → clear message, clean exit.
- **Command timeout** → reported to the player, retry allowed.
- **Device unplugged mid-game** → detected, offer reconnect or abort.
- **Wrong card type presented** → re-prompt (before the clock).
- **Guard block** → print reason, do not send, let the player retry.
- **Ctrl-C** → graceful quit, session closed properly.

## Known risk: output parsing

The verifiers parse the **text output** of the `pm3` client (pulling FC/CN out
of `lf hid reader`, UID out of `hf mf info`, etc.). That output format is
**client-version-specific**. Parsers will be written tolerantly (regex, not
fixed column positions) and then **calibrated against the player's actual
client output** on real hardware — expect a short tuning pass during
implementation on the device.

## Out of scope (v1)

- Simulated / no-hardware mode.
- Shuffled or difficulty-tiered challenge order.
- More than the single command guard.
- Multi-device support.
