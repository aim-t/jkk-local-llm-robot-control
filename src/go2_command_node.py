"""ROS 2 node: plain-language command in, checked robot command out.

It listens for text on /voice_command, asks the local language model to translate it,
runs the safety check, and publishes the result:

    /go2/command          approved commands, as JSON text, e.g.
                          {"action": "turn", "distance_m": 0.0, "angle_deg": 90.0}
    /go2/command_blocked  commands that were refused, with the reason

STOP (from the web page, the chat or send.py) also publishes on /llm/cancel. Then the answer
being worked on is abandoned, and commands that queued up behind it are dropped, so nothing
the model was busy with can move the robot after STOP. The node keeps running.

Nothing is sent to robot motors here. Turning an approved command into the Go2's own
movement messages is a separate step that depends on the lab's robot setup.

Run inside the ROS 2 container (see README), with Ollama running on the Mac:
    python3 /ws/src/go2_command_node.py
"""

import json
import time

import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Empty, String

from run_benchmark import Cancelled, ask
from safety import check, check_against_text

ANSWER_TIMEOUT_S = 10.0  # give up on the model after this long
STALE_S = 5.0            # an answer that took longer than this is not acted on
FLUSH_S = 0.3            # commands that arrive this soon after a cancelled one were queued behind it


class Go2CommandNode(Node):
    def __init__(self):
        super().__init__("go2_command_node")
        self.model = self.declare_parameter("model", "llama3.2:3b").value
        self.approved = self.create_publisher(String, "/go2/command", 10)
        self.blocked = self.create_publisher(String, "/go2/command_blocked", 10)
        self.cancel_time = 0.0
        self.flush_until = 0.0
        # Commands are handled one at a time; the cancel signal has its own group, so it is
        # received even while the node waits for the model.
        self.create_subscription(String, "/voice_command", self.on_command, 10,
                                 callback_group=MutuallyExclusiveCallbackGroup())
        self.create_subscription(Empty, "/llm/cancel", self.on_cancel, 10,
                                 callback_group=MutuallyExclusiveCallbackGroup())

        # Load the model now so the first real command is not slow.
        # Load the model now so the first real command is not slow. Loading can take a while.
        warmup = ask(self.model, "Stand up.", timeout=120)
        self.get_logger().info(f"{self.model} ready (loaded in {warmup['load_s']:.1f} s). Waiting on /voice_command")

    def on_cancel(self, _message):
        self.cancel_time = time.monotonic()
        self.get_logger().info("STOP: cancelling the command in progress and any queued ones")

    def cancelled_reply(self, text, why):
        self.publish(self.blocked, {"heard": text, "reason": why})
        self.get_logger().info(f"CANCELLED {text!r}: {why}")

    def on_command(self, message):
        text = message.data
        entered = time.monotonic()
        if entered < self.flush_until:  # was waiting in the queue when STOP came
            self.flush_until = entered + FLUSH_S
            self.cancelled_reply(text, "cancelled by STOP before the model started on it")
            return
        start = time.perf_counter()
        try:
            reply = ask(self.model, text, timeout=ANSWER_TIMEOUT_S,
                        cancelled=lambda: self.cancel_time > entered)["reply"]
        except Cancelled:
            self.flush_until = time.monotonic() + FLUSH_S
            self.cancelled_reply(text, "cancelled by STOP while the model was answering")
            return
        except Exception as error:  # network, timeout or a garbled answer: never move
            self.publish(self.blocked, {"heard": text, "reason": f"no usable answer from the model: {error}"})
            self.get_logger().error(f"no usable answer from the model: {error}")
            return
        command, reason = check(reply)
        command, reason = check_against_text(text, command) if command else (command, reason)
        elapsed = time.perf_counter() - start
        if command is not None and self.cancel_time > entered:
            # STOP came after the answer was complete but before it was sent on.
            self.flush_until = time.monotonic() + FLUSH_S
            self.cancelled_reply(text, "cancelled by STOP")
            return
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
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():  # rclpy.try_shutdown() exists only from ROS 2 Jazzy; the car runs Humble
            rclpy.shutdown()


if __name__ == "__main__":
    main()
