"""Type commands for the robot in plain language, one after another.

    python3 chat.py

Each line you type is sent on /voice_command. The answer from go2_command_node.py is shown:
what was approved and sent on to the dog, or why it was refused. Type "stop" (or just press
Enter on an empty line) to stop the robot at once without waiting for the language model.
Type "quit" to leave.
"""

import json
import threading
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.executors import SingleThreadedExecutor
from std_msgs.msg import String

REPLY_WAIT_S = 5.0


def describe(command):
    action = command["action"]
    if action == "move":
        d = command["distance_m"]
        return f"walk {'forward' if d >= 0 else 'backward'} {abs(d):g} m"
    if action == "turn":
        a = command["angle_deg"]
        return f"turn {'left' if a >= 0 else 'right'} {abs(a):g} degrees"
    return action.replace("_", " ")


def main():
    rclpy.init()
    node = rclpy.create_node("chat")
    text_pub = node.create_publisher(String, "/voice_command", 10)
    command_pub = node.create_publisher(String, "/go2/command", 10)
    cmd_vel_pub = node.create_publisher(Twist, "/cmd_vel", 10)

    replies = []
    got_reply = threading.Event()

    def on_reply(kind):
        def callback(message):
            replies.append((kind, json.loads(message.data)))
            got_reply.set()
        return callback

    node.create_subscription(String, "/go2/command", on_reply("approved"), 10)
    node.create_subscription(String, "/go2/command_blocked", on_reply("blocked"), 10)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    spinner = threading.Thread(target=executor.spin, daemon=True)
    spinner.start()
    time.sleep(1.0)  # let ROS connect

    print("Type a command for the robot. Empty line or 'stop' = stop now, 'quit' = leave.")
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            line = "quit"
        if line.lower() in ("", "stop"):
            command_pub.publish(String(data=json.dumps({"action": "stop", "distance_m": 0.0, "angle_deg": 0.0})))
            for _ in range(10):
                cmd_vel_pub.publish(Twist())
                time.sleep(0.02)
            print("robot> stopping")
            continue
        if line.lower() == "quit":
            break

        replies.clear()
        got_reply.clear()
        started = time.monotonic()
        text_pub.publish(String(data=line))
        if not got_reply.wait(REPLY_WAIT_S):
            print("robot> no answer. Is go2_command_node.py running, and ollama serve on the Mac?")
            continue
        kind, payload = replies[0]
        took = time.monotonic() - started
        if kind == "approved":
            print(f"robot> {describe(payload)}  ({took:.1f} s)")
        else:
            print(f"robot> refused: {payload.get('reason', 'unknown reason')}  ({took:.1f} s)")

    executor.shutdown()
    spinner.join(timeout=2.0)
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
