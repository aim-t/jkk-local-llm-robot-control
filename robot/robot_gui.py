"""The web console for a real robot: type or speak a command in the browser on the Mac.

    sim_mujoco/.venv/bin/python robot/robot_gui.py 192.168.123.95 car2
    then open http://localhost:8765            (robot/start_gui.sh does all of this)

It reuses the page, command history and speech recognition of the simulation console
(sim_mujoco/src/web_gui.py and speech.py), so it needs the sim_mujoco folder and its Python.
Instead of a simulation it talks to robot_bridge_node.py on the robot over UDP (port 9871).
The robot's own nodes (language model check, safety checks, movement) decide what happens,
exactly as with the terminal chat. There is no camera view; the path is drawn from /odom.
"""

import json
import math
import os
import socket
import sys
import threading
import time
from http.server import ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sim_mujoco", "src"))
import speech  # noqa: E402
import web_gui  # noqa: E402
from web_gui import CommandLog, make_handler  # noqa: E402

ROBOT_PORT = 9871
RATE_HZ = 20
LINK_TIMEOUT_S = 1.0


class RobotApp:
    """Same interface as web_gui.App, so the same page and request handler work."""

    send_speech = web_gui.App.send_speech  # speech -> text -> send_text, or a direct stop

    def __init__(self, robot_ip, robot_name):
        self.robot = (robot_ip, ROBOT_PORT)
        self.robot_name = robot_name
        self.lock = threading.Lock()
        self.log = CommandLog()
        self.frame = b""  # no camera
        self.path = []
        self.reset_requested = False
        self.shutdown_requested = False
        self.speech_status = "loading"
        self.pose = (0.0, 0.0, 0.0)
        self.velocity = (0.0, 0.0)
        self.commanded = (0.0, 0.0)
        self.odom_age = None
        self.robot_seen = 0.0
        self.started = time.monotonic()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)

    def request_shutdown(self):
        """The page's Shut down button: stop the robot, then end; start.sh stops everything else."""
        self.send_stop()
        self.shutdown_requested = True

    def bridge_connected(self):
        return time.monotonic() - self.robot_seen < LINK_TIMEOUT_S

    def send(self, message):
        try:
            self.sock.sendto(json.dumps(message).encode(), self.robot)
        except OSError:
            pass  # robot not reachable; shown as "not connected" on the page

    def send_text(self, text, mode="typed", speech_info=None):
        with self.lock:
            if not self.bridge_connected():
                self.log.add(text, status="not sent: the robot is not connected", mode=mode, speech_info=speech_info)
                return
            self.log.add(text, mode=mode, speech_info=speech_info)
            self.send({"type": "text", "text": text})

    def send_stop(self):
        for _ in range(3):  # UDP can drop a message; a stop must arrive
            self.send({"type": "stop"})

    def state(self):
        with self.lock:
            x, y, yaw = self.pose
            return {
                "mode": "robot",
                "robot": self.robot_name,
                "live": {"x": round(x, 2), "y": round(y, 2), "heading_deg": round(math.degrees(yaw), 1),
                         "speed": round(self.velocity[0], 2), "turn_rate": round(self.velocity[1], 2),
                         "height": None, "cmd_speed": round(self.commanded[0], 2),
                         "cmd_turn": round(self.commanded[1], 2), "falls": 0, "fps": 0,
                         "odom_age": self.odom_age, "sim_time": round(time.monotonic() - self.started)},
                "bridge": self.bridge_connected(),
                "speech": self.speech_status,
                "path": self.path[-1500:],
                "log": self.log.public(),
            }

    def run(self):
        step = 0
        next_tick = time.monotonic()
        while not self.shutdown_requested:
            self.send({"type": "hello"})
            with self.lock:
                self.read_network()
                if self.reset_requested:  # "Clear path" on the page
                    self.reset_requested = False
                    self.path.clear()
                commanded = abs(self.commanded[0]) > 1e-3 or abs(self.commanded[1]) > 1e-3
                self.log.update(self.pose, commanded)
                if step % 2 == 0 and self.bridge_connected():
                    self.path.append([round(self.pose[0], 3), round(self.pose[1], 3)])
            step += 1
            next_tick += 1.0 / RATE_HZ
            time.sleep(max(0.0, next_tick - time.monotonic()))

    def read_network(self):
        while True:
            try:
                packet = self.sock.recv(65536)
            except (BlockingIOError, ConnectionRefusedError):
                return
            try:
                message = json.loads(packet)
            except ValueError:
                continue
            self.robot_seen = time.monotonic()
            if message.get("type") == "state":
                self.pose = (message["x"], message["y"], message["yaw"])
                self.velocity = (message["vx"], message["wz"])
                self.commanded = (message["cmd_vx"], message["cmd_wz"])
                self.odom_age = message.get("odom_age")
            elif message.get("type") == "event":
                self.log.on_event(message["kind"], message["data"], self.pose)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    app = RobotApp(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "robot")

    def load_speech():
        try:
            speech.load()
            app.speech_status = "ready"
        except Exception as error:  # typing still works
            app.speech_status = f"unavailable ({error})"
    threading.Thread(target=load_speech, daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", web_gui.WEB_PORT), make_handler(app))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Open http://localhost:{web_gui.WEB_PORT} in your browser. Press Ctrl+C here to stop.", flush=True)
    try:
        app.run()
        print("Shut down from the web page.", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        app.send_stop()
        time.sleep(0.5)  # let the page see the last answer
        server.shutdown()


if __name__ == "__main__":
    main()
