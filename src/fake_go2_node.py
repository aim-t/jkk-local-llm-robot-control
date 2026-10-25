"""A stand-in for the robot, for testing without the Go2 or a simulator.

It listens to /cmd_vel and publishes where a robot obeying those speeds would be on /odom.
Real legs do not reach a new speed instantly, so the speed here changes gradually
(a simple lag, RESPONSE_TIME_S). This is a rough stand-in, not a model of the Go2.

Run inside the ROS 2 container:
    python3 /ws/src/fake_go2_node.py
"""

import math
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node

RATE_HZ = 50
RESPONSE_TIME_S = 0.3   # how quickly the speed follows the command
COMMAND_TIMEOUT_S = 0.5  # with no new command for this long, the robot slows to a halt


class FakeGo2(Node):
    def __init__(self):
        super().__init__("fake_go2")
        self.odom = self.create_publisher(Odometry, "/odom", 10)
        self.create_subscription(Twist, "/cmd_vel", self.on_cmd_vel, 10)
        self.create_timer(1.0 / RATE_HZ, self.step)
        self.x = self.y = self.yaw = 0.0
        self.v = self.w = 0.0                 # actual speeds
        self.target_v = self.target_w = 0.0   # commanded speeds
        self.last_command = 0.0
        self.last_step = time.monotonic()
        self.get_logger().info("Fake robot publishing /odom")

    def on_cmd_vel(self, message):
        self.target_v = message.linear.x
        self.target_w = message.angular.z
        self.last_command = time.monotonic()

    def step(self):
        now = time.monotonic()
        dt = now - self.last_step
        self.last_step = now
        if now - self.last_command > COMMAND_TIMEOUT_S:
            self.target_v = self.target_w = 0.0

        blend = 1.0 - math.exp(-dt / RESPONSE_TIME_S)
        self.v += (self.target_v - self.v) * blend
        self.w += (self.target_w - self.w) * blend
        self.yaw += self.w * dt
        self.x += self.v * math.cos(self.yaw) * dt
        self.y += self.v * math.sin(self.yaw) * dt

        message = Odometry()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = "odom"
        message.pose.pose.position.x = self.x
        message.pose.pose.position.y = self.y
        message.pose.pose.orientation.z = math.sin(self.yaw / 2)
        message.pose.pose.orientation.w = math.cos(self.yaw / 2)
        message.twist.twist.linear.x = self.v
        message.twist.twist.angular.z = self.w
        self.odom.publish(message)


def main():
    rclpy.init()
    node = FakeGo2()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
