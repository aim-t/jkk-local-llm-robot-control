"""ROS 2 node ON the robot that connects it to the web page on the Mac (robot_gui.py).

The Mac sends small UDP messages to this node (port 9871) and it answers to whoever sent the
last one, so only outgoing connections are needed from the Mac:
    Mac -> robot:  {"type": "hello"}             about 20 times a second, "the page is still open"
                   {"type": "text", "text": ...}  a typed or spoken command -> /voice_command
                   {"type": "stop"}               stop at once, without the language model
    robot -> Mac:  {"type": "state", ...}         position from /odom and the current speed command
                   {"type": "event", ...}         what go2_command_node.py approved or refused

Every message from the Mac must carry the session key in BRIDGE_TOKEN, which start.sh makes
fresh for each run. Messages without it are ignored, so other machines on the network cannot
command the robot. (UDP is not encrypted: someone listening on the same network could still
read the key. It stops casual or accidental use, not a determined attacker.)

Safety: if the page goes silent for LINK_TIMEOUT_S (laptop closed, Wi-Fi lost), this node
sends a stop, which also cancels what the language model is still working on.

Started by run_on_robot.sh when GUI=1.
"""

import hmac
import json
import os
import signal
import socket
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from std_msgs.msg import Empty, String

from cmd_vel_node import yaw_from_quaternion

PORT = 9871
RATE_HZ = 20
LINK_TIMEOUT_S = 1.5
STOP_COMMAND = json.dumps({"action": "stop", "distance_m": 0.0, "angle_deg": 0.0})


class RobotBridge(Node):
    def __init__(self):
        super().__init__("robot_bridge")
        self.token = os.environ.get("BRIDGE_TOKEN", "")
        if len(self.token) < 16:
            raise ValueError("BRIDGE_TOKEN (the session key from start.sh) is missing or too short")
        self.voice = self.create_publisher(String, "/voice_command", 10)
        self.command_pub = self.create_publisher(String, "/go2/command", 10)
        self.cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.cancel_pub = self.create_publisher(Empty, "/llm/cancel", 10)
        self.create_subscription(Odometry, "/odom", self.on_odom, 10)
        self.create_subscription(Twist, "/cmd_vel", self.on_cmd_vel, 10)
        for topic, kind in (("/go2/command", "approved"), ("/go2/command_blocked", "blocked"),
                            ("/go2/command_unsupported", "unsupported")):
            self.create_subscription(String, topic, self.forward_event(kind), 10)
        self.create_timer(1.0 / RATE_HZ, self.on_tick)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", PORT))
        self.sock.setblocking(False)
        self.client = None
        self.client_seen = 0.0
        self.pose = None
        self.odom_time = 0.0
        self.velocity = (0.0, 0.0)
        self.commanded = (0.0, 0.0)
        self.get_logger().info(f"Waiting for the web page on UDP port {PORT}")

    def send(self, message):
        if self.client:
            try:
                self.sock.sendto(json.dumps(message).encode(), self.client)
            except OSError:
                pass

    def stop(self, why):
        self.cancel_pub.publish(Empty())  # drop what the language model is still working on
        self.command_pub.publish(String(data=STOP_COMMAND))
        self.cmd_vel_pub.publish(Twist())
        self.get_logger().info(f"stop sent ({why})")

    def on_odom(self, message):
        p = message.pose.pose
        self.pose = (p.position.x, p.position.y, yaw_from_quaternion(p.orientation))
        self.velocity = (message.twist.twist.linear.x, message.twist.twist.angular.z)
        self.odom_time = time.monotonic()

    def on_cmd_vel(self, message):
        self.commanded = (message.linear.x, message.angular.z)

    def forward_event(self, kind):
        def callback(message):
            try:
                data = json.loads(message.data)
            except ValueError:
                return  # not ours or garbled; never let it end the session
            if isinstance(data, dict):
                self.send({"type": "event", "kind": kind, "data": data})
        return callback

    def on_tick(self):
        now = time.monotonic()
        while True:
            try:
                packet, sender = self.sock.recvfrom(4096)
            except BlockingIOError:
                break
            try:
                message = json.loads(packet)
            except ValueError:
                continue
            if not isinstance(message, dict) or not hmac.compare_digest(str(message.get("token", "")), self.token):
                continue  # not from our page
            if sender != self.client:
                self.get_logger().info(f"web page connected from {sender[0]}")
            self.client, self.client_seen = sender, now
            if message.get("type") == "text" and str(message.get("text", "")).strip():
                self.voice.publish(String(data=str(message["text"])[:300]))
            elif message.get("type") == "stop":
                self.stop("stop from the web page")

        if self.client and now - self.client_seen > LINK_TIMEOUT_S:
            # Always stop: a command may still be with the language model even if the robot is
            # standing still right now, and nobody is watching the page any more.
            self.stop("the web page went silent")
            self.get_logger().info("web page disconnected")
            self.client = None

        if self.client and self.pose:
            x, y, yaw = self.pose
            self.send({"type": "state", "x": x, "y": y, "yaw": yaw,
                       "vx": self.velocity[0], "wz": self.velocity[1],
                       "cmd_vx": self.commanded[0], "cmd_wz": self.commanded[1],
                       "odom_age": round(now - self.odom_time, 2)})


def main():
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))
    node = RobotBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop("bridge shutting down")
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
