"""Send one command into the pipeline from a terminal, without typing ROS message syntax.

    python3 send.py text "Walk forward one metre."   plain language, goes through the model
    python3 send.py move 0.3                         skip the model: move 0.3 m (negative = back)
    python3 send.py turn 90                          skip the model: turn 90 degrees (negative = right)
    python3 send.py stop                             stop at once

Moves and turns typed here go through the same safety check as the model's answers,
so a mistyped "move 30" is refused.

"stop" is sent twice over: as a stop command to cmd_vel_node, and as zero speed straight on
/cmd_vel, so it works even if cmd_vel_node is not running. It does not replace the robot's own
emergency stop through the Unitree API.
"""

import json
import sys
import time

import rclpy
from geometry_msgs.msg import Twist
from std_msgs.msg import Empty, String

from safety import check

USAGE = __doc__


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("text", "move", "turn", "stop"):
        sys.exit(USAGE)
    kind = sys.argv[1]

    rclpy.init()
    node = rclpy.create_node("send_command")
    text_pub = node.create_publisher(String, "/voice_command", 10)
    command_pub = node.create_publisher(String, "/go2/command", 10)
    cmd_vel_pub = node.create_publisher(Twist, "/cmd_vel", 10)
    cancel_pub = node.create_publisher(Empty, "/llm/cancel", 10)
    time.sleep(1.0)  # give ROS a moment to connect the publishers to their listeners

    if kind == "text":
        text_pub.publish(String(data=" ".join(sys.argv[2:])))
    elif kind == "stop":
        cancel_pub.publish(Empty())  # drop what the language model is still working on
        command_pub.publish(String(data=json.dumps({"action": "stop", "distance_m": 0.0, "angle_deg": 0.0})))
        for _ in range(10):
            cmd_vel_pub.publish(Twist())
            time.sleep(0.05)
    else:
        value = float(sys.argv[2])
        if kind == "move":
            request = {"action": "move", "distance_m": value, "direction": "none", "angle_deg": 0}
        else:
            request = {"action": "turn", "distance_m": 0, "angle_deg": abs(value),
                       "direction": "left" if value >= 0 else "right"}
        command, reason = check(json.dumps(request))
        if command is None:
            print(f"refused: {reason}")
            node.destroy_node()
            rclpy.shutdown()
            sys.exit(1)
        command_pub.publish(String(data=json.dumps(command)))

    time.sleep(0.5)  # let the message leave before the program exits
    print(f"sent: {kind} {' '.join(sys.argv[2:])}".strip())
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
