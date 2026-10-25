"""ROS 2 node: approved command in, velocity messages out on /cmd_vel.

It listens on /go2/command (the output of go2_command_node.py) and drives the robot with
geometry_msgs/Twist messages, the standard ROS way to say "go this fast, turn this fast".

A Twist only carries speeds, not distances. To know when to stop, the node watches the
robot's own position report on /odom and stops once the robot has actually travelled the
distance or turned the angle. A time limit stops it anyway if the target is never reached.

    move      linear.x  = +/- max_linear_speed   (positive = forward)
    turn      angular.z = +/- max_angular_speed  (positive = left, the ROS convention)
    stop      zero speed at once, cancelling any movement in progress
    stand_up, sit, lie_down   cannot be expressed as a speed; they are reported on
                              /go2/command_unsupported and nothing is sent

Speeds are ROS parameters, so they can be changed without editing code:
    python3 /ws/src/cmd_vel_node.py --ros-args -p max_linear_speed:=0.6
    ros2 param set /cmd_vel_node max_linear_speed 0.8      (while it is running)

With use_odom set to false the node falls back to timing: speed x time = distance.
"""

import json
import math
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String

PUBLISH_HZ = 20
ODOM_MAX_AGE_S = 0.5     # a position report older than this counts as missing
TIME_LIMIT_FACTOR = 2.0  # give up after twice the expected time, plus TIME_LIMIT_EXTRA_S
TIME_LIMIT_EXTRA_S = 2.0
# Near the target the speed is reduced so the robot does not overshoot while it slows down:
# speed = SLOWDOWN_GAIN x remaining distance (or angle), but never below the minimum.
SLOWDOWN_GAIN = 1.0      # per second
MIN_LINEAR_SPEED = 0.1   # metres per second
MIN_ANGULAR_SPEED = 0.15  # radians per second


def yaw_from_quaternion(q):
    """Heading in radians (rotation about the vertical axis) from a ROS orientation."""
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def angle_difference(a, b):
    """Smallest signed difference a - b, so crossing +/-180 degrees does not jump."""
    return math.atan2(math.sin(a - b), math.cos(a - b))


class CmdVelNode(Node):
    def __init__(self):
        super().__init__("cmd_vel_node")
        # The lab's suggested starting speed is 0.6 m/s.
        self.declare_parameter("max_linear_speed", 0.6)   # metres per second
        self.declare_parameter("max_angular_speed", 0.5)  # radians per second (about 29 degrees per second)
        self.declare_parameter("use_odom", True)

        self.cmd_vel = self.create_publisher(Twist, "/cmd_vel", 10)
        self.unsupported = self.create_publisher(String, "/go2/command_unsupported", 10)
        self.create_subscription(String, "/go2/command", self.on_command, 10)
        self.create_subscription(Odometry, "/odom", self.on_odom, 10)
        self.create_timer(1.0 / PUBLISH_HZ, self.on_tick)

        self.pose = None        # latest (x, y, yaw) from /odom
        self.pose_time = 0.0
        self.twist = None       # the speed being sent, or None when idle
        self.goal = None        # what has to be reached before stopping
        self.get_logger().info("Waiting on /go2/command")

    def param(self, name):
        return self.get_parameter(name).value

    def on_odom(self, message):
        p = message.pose.pose
        self.pose = (p.position.x, p.position.y, yaw_from_quaternion(p.orientation))
        self.pose_time = time.monotonic()
        if self.goal and self.goal["kind"] == "turn":
            # Add up small heading changes so a turn of more than 180 degrees is counted correctly.
            self.goal["turned"] += abs(angle_difference(self.pose[2], self.goal["last_yaw"]))
            self.goal["last_yaw"] = self.pose[2]

    def on_command(self, message):
        command = json.loads(message.data)
        action = command["action"]

        if action == "stop":
            self.halt("stop command")
        elif action == "move":
            distance = command["distance_m"]
            self.start("move", target=abs(distance),
                       linear=math.copysign(self.param("max_linear_speed"), distance))
        elif action == "turn":
            angle = math.radians(command["angle_deg"])
            self.start("turn", target=abs(angle),
                       angular=math.copysign(self.param("max_angular_speed"), angle))
        else:
            self.unsupported.publish(String(data=message.data))
            self.get_logger().warning(f"{action} cannot be sent on /cmd_vel; nothing sent")

    def start(self, kind, target, linear=0.0, angular=0.0):
        """Begin a movement. A new command replaces one that is still running."""
        speed = abs(linear) or abs(angular)
        if speed <= 0:
            self.halt("speed parameter is zero")
            return
        expected_s = target / speed
        use_odom = self.param("use_odom")
        if use_odom and not self.odom_is_fresh():
            self.halt("no recent /odom message, so the distance cannot be measured; movement refused")
            return

        self.goal = {
            "kind": kind,
            "target": target,
            "use_odom": use_odom,
            "start_pose": self.pose,
            "last_yaw": self.pose[2] if self.pose else 0.0,
            "turned": 0.0,
            "end_time": time.monotonic() + expected_s,
            "deadline": time.monotonic() + TIME_LIMIT_FACTOR * expected_s + TIME_LIMIT_EXTRA_S,
        }
        twist = Twist()
        twist.linear.x = linear
        twist.angular.z = angular
        self.twist = twist
        how = "until /odom shows it is done" if use_odom else f"for {expected_s:.2f} s"
        self.get_logger().info(f"{kind}: linear {linear:+.2f} m/s, angular {angular:+.2f} rad/s, {how}")

    def odom_is_fresh(self):
        return self.pose is not None and time.monotonic() - self.pose_time < ODOM_MAX_AGE_S

    def progress(self):
        """How far the current movement has got, in metres or radians."""
        goal = self.goal
        if goal["kind"] == "move":
            x0, y0, _ = goal["start_pose"]
            return math.hypot(self.pose[0] - x0, self.pose[1] - y0)
        return goal["turned"]

    def slow_down_near_target(self, remaining):
        if self.goal["kind"] == "move":
            top, low, value = self.param("max_linear_speed"), MIN_LINEAR_SPEED, self.twist.linear.x
        else:
            top, low, value = self.param("max_angular_speed"), MIN_ANGULAR_SPEED, self.twist.angular.z
        speed = math.copysign(max(min(low, top), min(top, SLOWDOWN_GAIN * remaining)), value)
        if self.goal["kind"] == "move":
            self.twist.linear.x = speed
        else:
            self.twist.angular.z = speed

    def halt(self, why):
        if self.goal and self.goal["use_odom"] and self.pose:
            done = self.progress()
            unit = "m" if self.goal["kind"] == "move" else "deg"
            done = done if unit == "m" else math.degrees(done)
            why += f"; measured {done:.2f} {unit}"
        self.twist = None
        self.goal = None
        self.cmd_vel.publish(Twist())  # a Twist with no values set is all zeros
        self.get_logger().info(f"zero speed sent ({why})")

    def on_tick(self):
        """Runs 20 times a second: keep sending the speed until the movement is done."""
        if self.twist is None:
            return
        now = time.monotonic()
        goal = self.goal
        if goal["use_odom"]:
            if not self.odom_is_fresh():
                self.halt("/odom stopped arriving")
                return
            remaining = goal["target"] - self.progress()
            if remaining <= 0:
                self.halt("target reached")
                return
            if now >= goal["deadline"]:
                self.halt("time limit reached before the target")
                return
            self.slow_down_near_target(remaining)
        elif now >= goal["end_time"]:
            self.halt("movement time finished")
            return
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
