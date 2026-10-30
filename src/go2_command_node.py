"""ROS 2 node: plain-language command in, checked robot command out.

It listens for text on /voice_command, asks the local language model to translate it,
runs the safety check, and publishes the result:

    /go2/command          approved commands, as JSON text, e.g.
                          {"action": "turn", "distance_m": 0.0, "angle_deg": 90.0}
    /go2/command_blocked  commands that were refused, with the reason

Nothing is sent to robot motors here. Turning an approved command into the Go2's own
movement messages is a separate step that depends on the lab's robot setup.

Run inside the ROS 2 container (see README), with Ollama running on the Mac:
    python3 /ws/src/go2_command_node.py
"""

import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from run_benchmark import ask
from safety import check, check_against_text

ANSWER_TIMEOUT_S = 10.0  # give up on the model after this long
STALE_S = 5.0            # an answer that took longer than this is not acted on


class Go2CommandNode(Node):
    def __init__(self):
        super().__init__("go2_command_node")
        self.model = self.declare_parameter("model", "llama3.2:3b").value
        self.approved = self.create_publisher(String, "/go2/command", 10)
        self.blocked = self.create_publisher(String, "/go2/command_blocked", 10)
        self.create_subscription(String, "/voice_command", self.on_command, 10)

        # Load the model now so the first real command is not slow.
        # Load the model now so the first real command is not slow. Loading can take a while.
        warmup = ask(self.model, "Stand up.", timeout=120)
        self.get_logger().info(f"{self.model} ready (loaded in {warmup['load_s']:.1f} s). Waiting on /voice_command")

    def on_command(self, message):
        text = message.data
        start = time.perf_counter()
        try:
            reply = ask(self.model, text, timeout=ANSWER_TIMEOUT_S)["reply"]
        except Exception as error:  # network, timeout or a garbled answer: never move
            self.publish(self.blocked, {"heard": text, "reason": f"no usable answer from the model: {error}"})
            self.get_logger().error(f"no usable answer from the model: {error}")
            return
        command, reason = check(reply)
        command, reason = check_against_text(text, command) if command else (command, reason)
        elapsed = time.perf_counter() - start
        if command is not None and elapsed > STALE_S:
            # The person may have moved on (or said stop) while the model was slow.
            command, reason = None, f"the answer took {elapsed:.1f} s, so it was not acted on"

        if command is None:
            self.publish(self.blocked, {"heard": text, "reason": reason, "model_reply": reply})
            self.get_logger().warning(f"BLOCKED {text!r}: {reason} ({elapsed:.2f} s)")
        else:
            self.publish(self.approved, command)
            self.get_logger().info(f"APPROVED {text!r} -> {json.dumps(command)} ({elapsed:.2f} s)")

    def publish(self, publisher, payload):
        publisher.publish(String(data=json.dumps(payload, ensure_ascii=False)))


def main():
    rclpy.init()
    node = Go2CommandNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
