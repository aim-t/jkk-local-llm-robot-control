"""ROS 2 node for F1TENTH cars: Twist on /cmd_vel in, AckermannDriveStamped on /drive out.

cmd_vel_node.py speaks Twist (forward speed and turning rate), the general ROS format.
An F1TENTH car is driven with speed and a steering angle instead. For a car with wheelbase L,
driving at speed v and turning at rate w means a steering angle of atan(L * w / v).

Safety:
- The steering angle is limited to max_steering_angle; a sharper request becomes a wider curve,
  and cmd_vel_node.py, which measures the turn with /odom, simply keeps going until it is done.
- A turn requested with no forward speed (a legged robot's turn on the spot) is impossible for
  a car, so the car is told to stand still.
- Drive messages are sent only while fresh Twist messages arrive. If they stop for longer than
  stale_after_s, zero speed is sent a few times and then nothing, so ackermann_mux's own timeout
  also stops the car.

Runs on the robot (started by run_on_robot.sh):
    python3 twist_to_ackermann_node.py --ros-args -p wheelbase:=0.25 -p max_steering_angle:=0.28
"""

import math
import signal
import time

import rclpy
from ackermann_msgs.msg import AckermannDriveStamped
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions

RATE_HZ = 20
ZERO_REPEATS = 5


class TwistToAckermann(Node):
    def __init__(self):
        super().__init__("twist_to_ackermann")
        # car2: wheelbase 0.25 m (vesc_to_odom in its vesc.yaml). Its servo range 0.15-0.85 with gain
        # -1.2135 and offset 0.5 allows about +/-0.29 rad, so 0.28 rad keeps a small margin.
        self.wheelbase = self.declare_parameter("wheelbase", 0.25).value
        self.max_steering = self.declare_parameter("max_steering_angle", 0.28).value
        self.stale_after = self.declare_parameter("stale_after_s", 0.3).value
        drive_topic = self.declare_parameter("drive_topic", "/drive").value
        if not (0.1 <= self.wheelbase <= 1.0 and 0.05 <= self.max_steering <= 0.6):
            raise ValueError("wheelbase must be 0.1-1.0 m and max_steering_angle 0.05-0.6 rad")

        self.drive = self.create_publisher(AckermannDriveStamped, drive_topic, 10)
        self.create_subscription(Twist, "/cmd_vel", self.on_twist, 10)
        self.create_timer(1.0 / RATE_HZ, self.on_tick)
        self.speed = 0.0
        self.steering = 0.0
        self.last_twist = 0.0
        self.zeros_left = 0
        self.get_logger().info(f"Converting /cmd_vel to {drive_topic} (wheelbase {self.wheelbase} m, "
                               f"steering limit {self.max_steering} rad)")

    def on_twist(self, message):
        v, w = message.linear.x, message.angular.z
        if not (math.isfinite(v) and math.isfinite(w)):
            v, w = 0.0, 0.0
        if abs(v) < 1e-3:
            if abs(w) > 1e-3:
                self.get_logger().warning("a car cannot turn on the spot; standing still")
            v, steering = 0.0, 0.0
        else:
            steering = math.atan(self.wheelbase * w / v)
            steering = max(-self.max_steering, min(self.max_steering, steering))
        self.speed, self.steering = v, steering
        self.last_twist = time.monotonic()
        if v == 0.0:
            self.zeros_left = ZERO_REPEATS

    def send(self, speed, steering):
        message = AckermannDriveStamped()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = "base_link"
        message.drive.speed = float(speed)
        message.drive.steering_angle = float(steering)
        self.drive.publish(message)

    def on_tick(self):
        fresh = time.monotonic() - self.last_twist < self.stale_after
        if fresh and self.speed != 0.0:
            self.send(self.speed, self.steering)
        elif self.zeros_left > 0 or (not fresh and self.speed != 0.0):
            # Stopping: either asked to, or the Twist messages stopped coming.
            if not fresh and self.speed != 0.0:
                self.get_logger().info("no fresh /cmd_vel; stopping")
                self.speed, self.zeros_left = 0.0, ZERO_REPEATS
            self.send(0.0, 0.0)
            self.zeros_left -= 1


def main():
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))
    node = TwistToAckermann()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        for _ in range(ZERO_REPEATS):
            node.send(0.0, 0.0)
            time.sleep(0.02)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
