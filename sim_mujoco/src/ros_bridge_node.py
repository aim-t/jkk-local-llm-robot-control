"""ROS 2 side of the MuJoCo simulation. Runs in the ROS 2 Docker container.

Subscribes to /cmd_vel and forwards the speed to the simulation on the Mac over UDP.
Publishes what the simulated dog reports back as /odom, the same topic the real Go2 publishes.

For the web page (web_gui.py) it also carries:
    page -> ROS:  typed text, published on /voice_command; a stop request
    ROS -> page:  what go2_command_node.py approved or refused, and unsupported commands

    python3 /ws/sim_mujoco/src/ros_bridge_node.py
The Mac's address defaults to host.docker.internal, which Docker Desktop provides.
"""

import json
import math
import os
import socket

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String

SIM_ADDRESS = (os.environ.get("SIM_HOST", "host.docker.internal"), 9870)
RATE_HZ = 50
STOP_COMMAND = json.dumps({"action": "stop", "distance_m": 0.0, "angle_deg": 0.0})


class MujocoBridge(Node):
    def __init__(self):
        super().__init__("mujoco_bridge")
        self.odom = self.create_publisher(Odometry, "/odom", 10)
        self.voice = self.create_publisher(String, "/voice_command", 10)
        self.command_pub = self.create_publisher(String, "/go2/command", 10)
        self.cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(Twist, "/cmd_vel", self.on_cmd_vel, 10)
        for topic, kind in (("/go2/command", "approved"), ("/go2/command_blocked", "blocked"),
                            ("/go2/command_unsupported", "unsupported")):
            self.create_subscription(String, topic, self.forward_event(kind), 10)
        self.create_timer(1.0 / RATE_HZ, self.on_tick)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.command = {"vx": 0.0, "vy": 0.0, "wz": 0.0}
        self.get_logger().info(f"Bridging /cmd_vel and /odom to the simulation at {SIM_ADDRESS[0]}:{SIM_ADDRESS[1]}")

    def send(self, message):
        try:
            self.sock.sendto(json.dumps(message).encode(), SIM_ADDRESS)
        except OSError:
            pass  # simulation not running yet

    def on_cmd_vel(self, message):
        self.command = {"vx": message.linear.x, "vy": message.linear.y, "wz": message.angular.z}

    def forward_event(self, kind):
        def callback(message):
            self.send({"type": "event", "kind": kind, "data": json.loads(message.data)})
        return callback

    def on_tick(self):
        # Sending every tick also tells the simulation the bridge is still alive.
        self.send({"type": "cmd_vel", **self.command})
        while True:
            try:
                packet = self.sock.recv(65536)
            except (BlockingIOError, ConnectionRefusedError):
                return
            message = json.loads(packet)
            kind = message.get("type", "state")
            if kind == "state":
                self.publish_odom(message)
            elif kind == "text":
                self.voice.publish(String(data=message["text"]))
            elif kind == "stop":
                self.command_pub.publish(String(data=STOP_COMMAND))
                self.cmd_vel_pub.publish(Twist())

    def publish_odom(self, state):
        message = Odometry()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = "odom"
        message.child_frame_id = "base_link"
        message.pose.pose.position.x = state["x"]
        message.pose.pose.position.y = state["y"]
        message.pose.pose.orientation.z = math.sin(state["yaw"] / 2)
        message.pose.pose.orientation.w = math.cos(state["yaw"] / 2)
        message.twist.twist.linear.x = state["vx"]
        message.twist.twist.angular.z = state["wz"]
        self.odom.publish(message)


def main():
    rclpy.init()
    node = MujocoBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
