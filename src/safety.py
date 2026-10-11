"""Check a model's reply before it is allowed to reach the robot.

The language model is not fully reliable, so its reply is never sent to the robot directly.
check() looks at the reply and either returns a clean command or blocks it with a reason.
The rules are plain code, so they behave the same way every time.

Replay saved benchmark results to see what the check would have blocked:
    .venv/bin/python src/safety.py results/20261012-004724_llama3.2-3b.json
"""

import json
import math
import sys

from run_benchmark import ACTIONS, is_correct, signed_angle

# Limits for a single command. Anything larger is refused, whatever the model says.
MAX_DISTANCE_M = 5.0
MAX_ANGLE_DEG = 180.0

POSTURE_ACTIONS = {"stand_up", "sit", "lie_down", "stop"}


def check(reply):
    """Return (command, reason). command is None when the reply is blocked."""
    try:
        got = json.loads(reply)
    except (json.JSONDecodeError, TypeError):
        return None, "reply is not valid JSON"
    if not isinstance(got, dict):
        return None, "reply is not a JSON object"

    action = got.get("action")
    if action not in ACTIONS:
        return None, f"action {action!r} is not in the allowed list"
    if action == "unknown":
        return None, "model did not recognise a command the robot can do"

    try:
        distance = float(got.get("distance_m", 0))
        angle = float(got.get("angle_deg", 0))
    except (TypeError, ValueError):
        return None, "distance or angle is not a number"
    if not (math.isfinite(distance) and math.isfinite(angle)):
        return None, "distance or angle is not a finite number"
    direction = got.get("direction", "none")

    # A reply that mixes fields from different actions means the model was confused.
    if action == "move":
        if distance == 0:
            return None, "move with zero distance"
        if abs(distance) > MAX_DISTANCE_M:
            return None, f"distance {distance} m is over the {MAX_DISTANCE_M} m limit"
        if angle != 0 or direction != "none":
            return None, "move must not include a turn"
    elif action == "turn":
        if direction not in ("left", "right"):
            return None, "turn without a left or right direction"
        if not 0 < abs(angle) <= MAX_ANGLE_DEG:
            return None, f"angle {angle} is outside 0 to {MAX_ANGLE_DEG} degrees"
        if distance != 0:
            return None, "turn must not include a distance"
    elif action in POSTURE_ACTIONS:
        if distance != 0 or angle != 0:
            return None, f"{action} must not include a distance or angle"

    command = {
        "action": action,
        "distance_m": distance,
        "angle_deg": signed_angle(got) if action == "turn" else 0.0,
    }
    return command, "ok"


def replay(path):
    """Apply check() to every answer in a saved results file and count the outcomes."""
    with open(path, encoding="utf-8") as f:
        report = json.load(f)
    rows = [row for row in report["rows"] if row["repeat"] == 0]

    sent_right, sent_wrong, blocked_wrong, refused_right, blocked_right = [], [], [], [], []
    for row in rows:
        command, reason = check(row["reply"])
        # Score again with today's rules instead of trusting the flag stored in an older file.
        _, correct = is_correct(row["reply"], row["expected"], row.get("category"))
        if command is not None:
            (sent_right if correct else sent_wrong).append((row, reason))
        elif not correct:
            blocked_wrong.append((row, reason))
        elif row["expected"]["action"] == "unknown":
            refused_right.append((row, reason))
        else:
            blocked_right.append((row, reason))

    print(f"\n{report['model']['name']}  ({path})")
    print(f"  commands                               {len(rows)}")
    print(f"  correct and sent to the robot          {len(sent_right)}")
    print(f"  correctly refused (nothing sent)       {len(refused_right)}")
    print(f"  wrong, blocked by the check            {len(blocked_wrong)}")
    print(f"  WRONG AND SENT TO THE ROBOT            {len(sent_wrong)}")
    print(f"  correct but blocked by a limit         {len(blocked_right)}")
    for title, group in (
        ("wrong and sent", sent_wrong),
        ("wrong, blocked", blocked_wrong),
        ("correct but blocked", blocked_right),
    ):
        for row, reason in group:
            reply = " ".join(row["reply"].split())
            print(f"    [{title}] {row['command']!r} -> {reply}  ({reason})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for results_file in sys.argv[1:]:
        replay(results_file)
