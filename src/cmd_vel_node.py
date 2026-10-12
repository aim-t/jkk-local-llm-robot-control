"""ROS 2 node: approved command in, velocity messages out on /cmd_vel.

It listens on /go2/command (the output of go2_command_node.py) and drives the robot with
geometry_msgs/Twist messages, the standard ROS way to say "go this fast, turn this fast".

A Twist only carries speeds, not distances, so a distance is turned into time:
"move 2 m" at 0.3 m/s means sending that speed for about 6.7 seconds, then zero.
The robot's real position is not measured here, so the distance is approximate.

    move      linear.x  = +/- LINEAR_SPEED   (positive = forward)
    turn      angular.z = +/- ANGULAR_SPEED  (positive = left, the ROS convention)
    stop      zero speed at once, cancelling any movement in progress
    stand_up, sit, lie_down   cannot be expressed as a speed; they are reported on
                              /go2/command_unsupported and nothing is sent

Run inside the ROS 2 container (see README):
    python3 /ws/src/cmd_vel_node.py
"""

import json
import math
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import String

# Deliberately slow first values. Agree the real ones with the lab before using the robot.
LINEAR_SPEED = 0.3   # metres per second
ANGULAR_SPEED = 0.5  # radians per second (about 29 degrees per second)
PUBLISH_HZ = 20


class CmdVelNode(Node):
    def __init__(self):
        super().__init__("cmd_vel_node")
        self.cmd_vel = self.create_publisher(Twist, "/cmd_vel", 10)
        self.unsupported = self.create_publisher(String, "/go2/command_unsupported", 10)
        self.create_subscription(String, "/go2/command", self.on_command, 10)
        self.create_timer(1.0 / PUBLISH_HZ, self.on_tick)

        self.twist = None   # the speed being sent, or None when idle
        self.end_time = 0.0
        self.get_logger().info("Waiting on /go2/command")

    def on_command(self, message):
        command = json.loads(message.data)
        action = command["action"]

        if action == "stop":
            self.halt("stop command")
        elif action == "move":
            distance = command["distance_m"]
            self.start(linear=math.copysign(LINEAR_SPEED, distance), seconds=abs(distance) / LINEAR_SPEED)
        elif action == "turn":
            angle = math.radians(command["angle_deg"])
            self.start(angular=math.copysign(ANGULAR_SPEED, angle), seconds=abs(angle) / ANGULAR_SPEED)
        else:
            self.unsupported.publish(String(data=message.data))
            self.get_logger().warning(f"{action} cannot be sent on /cmd_vel; nothing sent")

    def start(self, linear=0.0, angular=0.0, seconds=0.0):
        """Begin a timed movement. A new command replaces one that is still running."""
        twist = Twist()
        twist.linear.x = linear
        twist.angular.z = angular
        self.twist = twist
        self.end_time = time.monotonic() + seconds
        self.get_logger().info(f"linear {linear:+.2f} m/s, angular {angular:+.2f} rad/s for {seconds:.2f} s")

    def halt(self, why):
        self.twist = None
        self.cmd_vel.publish(Twist())  # a Twist with no values set is all zeros
        self.get_logger().info(f"zero speed sent ({why})")

    def on_tick(self):
        """Runs 20 times a second: keep sending the speed until the time is up."""
        if self.twist is None:
            return
        if time.monotonic() >= self.end_time:
            self.halt("movement finished")
        else:
            self.cmd_vel.publish(self.twist)


def main():
    rclpy.init()
    node = CmdVelNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cmd_vel.publish(Twist())
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
