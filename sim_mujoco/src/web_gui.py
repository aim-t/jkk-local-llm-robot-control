"""Web page for the simulated Go2: type a command, watch the dog, see whether it worked.

    sim_mujoco/.venv/bin/python sim_mujoco/src/web_gui.py
    then open http://localhost:8765

This replaces run_sim.py when you want the page: it runs the same simulation and talks to
ros_bridge_node.py in the same way (UDP port 9870), so the language model, safety check and
cmd_vel_node.py in the ROS 2 container decide what the dog does, exactly as on the robot.

Each typed command is followed from start to finish:
    sent -> answered by go2_command_node.py (approved or refused, and how long the model took)
         -> the dog moves -> the movement ends -> measured distance or angle against the target.
A move counts as successful within 10 cm or 10 % of the target, a turn within 10 degrees
or 10 %. These tolerances are this page's own choice, not a standard.

Commands can be typed or spoken. Spoken commands are recorded in the browser while the
microphone button is held, turned into text by a local Whisper model (speech.py), and then
go through exactly the same pipeline as typed text. A spoken "stop" skips the model.

The web server and images use only Python's standard library; speech uses pywhispercpp.
"""

import json
import math
import os
import re
import socket
import struct
import threading
import time
import zlib
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import mujoco
import numpy as np

import speech
from go2_sim import Go2Sim

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "web", "index.html")
WEB_PORT = int(os.environ.get("GUI_PORT", 8765))  # another page already on 8765? set GUI_PORT
UDP_PORT = 9870
STEP_S = 0.02            # one policy step
RENDER_EVERY = 3         # draw a picture every 3 steps, about 16 per second
COMMAND_TIMEOUT_S = 0.5  # no /cmd_vel for this long: stand still
ANSWER_TIMEOUT_S = 8.0   # no answer from the language node for this long: give up
SETTLE_S = 0.4           # speed must stay zero this long before a movement counts as finished
POSTURES = ("stand_up", "sit", "lie_down")
# A spoken stop skips the language model, like the STOP button, so it acts at once.
SPOKEN_STOP = re.compile(r"^\W*(stop|halt|freeze|stop now|stop stop|stop stop stop)\W*$", re.IGNORECASE)


def encode_png(image):
    """RGB numpy image to PNG bytes, using only zlib."""
    height, width, _ = image.shape
    raw = b"".join(b"\x00" + image[row].tobytes() for row in range(height))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b""))


def wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


class CommandLog:
    """Every command typed on the page, and what became of it."""

    def __init__(self):
        self.entries = []
        self.moving = None  # the entry whose movement is being measured
        self.ignore_stop_until = 0.0  # the stop we sent comes back as an event; it has its row already

    def add(self, text, status="waiting for the language model", mode="typed", speech_info=None):
        entry = {"id": len(self.entries) + 1, "text": text, "time": datetime.now().strftime("%H:%M:%S"),
                 "mode": mode, "speech": speech_info,
                 "sent": time.monotonic(), "status": status, "answer": None, "reason": None,
                 "model_s": None, "target": None, "achieved": None, "error": None, "unit": None,
                 "duration_s": None, "success": None}
        self.entries.append(entry)
        return entry

    def stop_pressed(self, pose, text="(stop button)", mode="button", speech_info=None):
        """STOP: the movement ends, and commands still waiting for the model are cancelled."""
        for waiting in self.entries:
            if waiting["status"] == "waiting for the language model":
                waiting.update(status="cancelled by STOP", success=None)
        self.finish_moving(pose, "interrupted by stop")
        entry = self.add(text, status="done", mode=mode, speech_info=speech_info)
        entry.update(success=True, answer={"action": "stop"}, model_s=0.0)
        self.ignore_stop_until = time.monotonic() + 3.0
        return entry

    def oldest_waiting(self):
        return next((e for e in self.entries if e["status"] == "waiting for the language model"), None)

    def on_event(self, kind, data, pose):
        if kind == "unsupported":
            return  # already handled when the posture command was approved
        entry = self.oldest_waiting()
        if kind == "blocked" and str(data.get("reason", "")).startswith("cancelled"):
            if entry is not None:  # cancelled by a STOP from elsewhere (e.g. the chat on the robot)
                entry.update(status="cancelled by STOP", success=None)
            return
        if entry is None and data.get("action") == "stop" and time.monotonic() < self.ignore_stop_until:
            self.finish_moving(pose, "interrupted by stop")
            return  # our own STOP coming back; it already has its row
        if entry is None:  # e.g. a stop sent from the chat on the robot
            entry = self.add("(stop from elsewhere)" if data.get("action") == "stop" else "(sent from elsewhere)")
        entry["model_s"] = round(time.monotonic() - entry["sent"], 2)

        if kind == "blocked":
            entry.update(status="refused by the safety check", reason=data.get("reason"), success=None)
            entry["answer"] = data.get("model_reply")
            return

        action = data["action"]
        entry["answer"] = data
        if action == "stop":
            self.finish_moving(pose, "interrupted by stop")
            entry.update(status="done", success=True)
        elif action in POSTURES:
            entry.update(status="not available in the simulation", success=None)
        else:
            self.finish_moving(pose, "replaced by the next command")
            is_move = action == "move"
            entry.update(status="moving", unit="m" if is_move else "deg",
                         target=data["distance_m"] if is_move else data["angle_deg"])
            entry["_start"] = pose
            entry["_turned"] = 0.0
            entry["_last_yaw"] = pose[2]
            entry["_began"] = time.monotonic()
            entry["_moved"] = False
            entry["_still_since"] = None
            self.moving = entry

    def progress(self, entry, pose):
        if entry["unit"] == "m":
            x0, y0, yaw0 = entry["_start"]
            return (pose[0] - x0) * math.cos(yaw0) + (pose[1] - y0) * math.sin(yaw0)
        return math.degrees(entry["_turned"])

    def update(self, pose, commanded):
        now = time.monotonic()
        for entry in self.entries:
            if entry["status"] == "waiting for the language model" and now - entry["sent"] > ANSWER_TIMEOUT_S:
                entry.update(status="no answer: is go2_command_node.py running?", success=False)
        entry = self.moving
        if entry is None:
            return
        entry["_turned"] += wrap(pose[2] - entry["_last_yaw"])
        entry["_last_yaw"] = pose[2]
        entry["achieved"] = round(self.progress(entry, pose), 2 if entry["unit"] == "m" else 1)
        if commanded:
            entry["_moved"], entry["_still_since"] = True, None
        elif entry["_moved"]:
            entry["_still_since"] = entry["_still_since"] or now
            if now - entry["_still_since"] > SETTLE_S:
                self.finish_moving(pose, "done")
        elif now - entry["_began"] > 3.0:
            self.finish_moving(pose, "the dog never received a speed: is cmd_vel_node.py running?")

    def finish_moving(self, pose, how):
        entry, self.moving = self.moving, None
        if entry is None:
            return
        achieved = self.progress(entry, pose)
        target = entry["target"]
        error = achieved - target
        if entry["unit"] == "m":
            ok = abs(error) <= max(0.10, 0.10 * abs(target))
        else:
            ok = abs(error) <= max(10.0, 0.10 * abs(target))
        entry.update(status=how, achieved=round(achieved, 2 if entry["unit"] == "m" else 1),
                     error=round(error, 2 if entry["unit"] == "m" else 1), success=ok if how == "done" else None,
                     duration_s=round(time.monotonic() - entry["_began"], 1))

    def public(self):
        return [{k: v for k, v in e.items() if not k.startswith("_")} for e in reversed(self.entries[-50:])]


class App:
    def __init__(self):
        self.sim = Go2Sim(os.path.join(ROOT, "go2", "scene.xml"), os.path.join(ROOT, "policy", "model_7850.pt"))
        self.lock = threading.Lock()
        self.log = CommandLog()
        self.frame = b""
        self.path = []
        self.falls = 0
        self.bridge = None
        self.bridge_seen = 0.0
        self.last_cmd_vel = 0.0
        self.reset_requested = False
        self.speech_status = "loading"
        self.fps = 0.0
        self.started = time.monotonic()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", UDP_PORT))
        self.sock.setblocking(False)

    # ---- called from the web server's threads ----
    def send_text(self, text, mode="typed", speech_info=None):
        with self.lock:
            if not self.bridge_connected():
                self.log.add(text, status="not sent: the ROS 2 bridge is not running", mode=mode, speech_info=speech_info)
                return
            self.log.add(text, mode=mode, speech_info=speech_info)
            self.sock.sendto(json.dumps({"type": "text", "text": text}).encode(), self.bridge)

    def send_speech(self, pcm_bytes):
        """Raw 16 kHz, 16-bit mono sound from the page -> text -> the same path as typed text."""
        samples = np.frombuffer(pcm_bytes[: len(pcm_bytes) // 2 * 2], dtype=np.int16)
        text, info = speech.transcribe(samples)
        if not text:
            with self.lock:
                self.log.add("(nothing understood)", status=f"not sent: {info.get('error')}", mode="spoken", speech_info=info)
            return {"text": "", "sent": False, **info}
        if SPOKEN_STOP.match(text):
            self.send_stop(text, "spoken", info)
            return {"text": text, "sent": True, "fast_stop": True, **info}
        self.send_text(text, mode="spoken", speech_info=info)
        return {"text": text, "sent": True, **info}

    def send_stop(self, text="(stop button)", mode="button", speech_info=None):
        """STOP: end the movement and cancel what the language model is working on."""
        with self.lock:
            self.sim.command[:] = 0.0  # stop at once on this side too
            self.log.stop_pressed(self.sim.pose(), text, mode, speech_info)
            if self.bridge_connected():
                self.sock.sendto(json.dumps({"type": "stop"}).encode(), self.bridge)

    def bridge_connected(self):
        return self.bridge is not None and time.monotonic() - self.bridge_seen < 1.0

    def state(self):
        with self.lock:
            sim = self.sim
            x, y, yaw = sim.pose()
            body_v = sim.base_rotation().T @ sim.data.qvel[0:3]
            return {
                "live": {"x": round(x, 2), "y": round(y, 2), "heading_deg": round(math.degrees(yaw), 1),
                         "speed": round(float(body_v[0]), 2), "turn_rate": round(float(sim.data.qvel[5]), 2),
                         "height": round(float(sim.data.qpos[2]), 2),
                         "cmd_speed": round(float(sim.command[0]), 2), "cmd_turn": round(float(sim.command[2]), 2),
                         "falls": self.falls, "fps": round(self.fps, 1),
                         "sim_time": round(time.monotonic() - self.started)},
                "bridge": self.bridge_connected(),
                "speech": self.speech_status,
                "path": self.path[-1500:],
                "log": self.log.public(),
            }

    # ---- the simulation loop, on the main thread (MuJoCo drawing needs it on a Mac) ----
    def run(self):
        renderer = mujoco.Renderer(self.sim.model, height=360, width=640)
        camera = mujoco.MjvCamera()
        camera.type = mujoco.mjtCamera.mjCAMERA_TRACKING
        camera.trackbodyid = 1
        camera.distance, camera.elevation, camera.azimuth = 2.2, -20, 135
        step, frames, fps_clock = 0, 0, time.monotonic()
        next_step = time.monotonic()
        while True:
            now = time.monotonic()
            with self.lock:
                self.read_network(now)
                if now - self.last_cmd_vel > COMMAND_TIMEOUT_S:
                    self.sim.command[:] = 0.0
                if self.reset_requested:
                    self.reset_requested = False
                    self.log.finish_moving(self.sim.pose(), "interrupted by reset")
                    self.sim.reset()
                    self.path.clear()
                self.sim.step()
                if self.sim.has_fallen():
                    self.falls += 1
                    self.log.finish_moving(self.sim.pose(), "interrupted: the dog fell")
                    self.sim.reset()
                pose = self.sim.pose()
                commanded = abs(self.sim.command[0]) > 1e-3 or abs(self.sim.command[2]) > 1e-3
                self.log.update(pose, commanded)
                if self.bridge:
                    body_vx = float((self.sim.base_rotation().T @ self.sim.data.qvel[0:3])[0])
                    state = {"type": "state", "x": pose[0], "y": pose[1], "yaw": pose[2],
                             "vx": body_vx, "wz": float(self.sim.data.qvel[5])}
                    self.sock.sendto(json.dumps(state).encode(), self.bridge)
                if step % 5 == 0:
                    self.path.append([round(pose[0], 3), round(pose[1], 3)])
                if step % RENDER_EVERY == 0:
                    renderer.update_scene(self.sim.data, camera)
                    image = renderer.render()
            if step % RENDER_EVERY == 0:
                png = encode_png(image)
                frames += 1
                with self.lock:
                    self.frame = png
            if now - fps_clock >= 1.0:
                self.fps, frames, fps_clock = frames / (now - fps_clock), 0, now
            step += 1
            next_step += STEP_S
            time.sleep(max(0.0, next_step - time.monotonic()))
            if time.monotonic() - next_step > 0.5:  # fell far behind (e.g. laptop slept): catch up
                next_step = time.monotonic()

    def read_network(self, now):
        while True:
            try:
                packet, sender = self.sock.recvfrom(65536)
            except BlockingIOError:
                return
            message = json.loads(packet)
            self.bridge, self.bridge_seen = sender, now
            if message.get("type") == "cmd_vel":
                self.sim.command[:] = [message.get("vx", 0.0), message.get("vy", 0.0), message.get("wz", 0.0)]
                self.last_cmd_vel = now
            elif message.get("type") == "event":
                self.log.on_event(message["kind"], message["data"], self.sim.pose())


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # keep the terminal quiet

        def reply(self, body, content_type, status=200):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                with open(PAGE, "rb") as f:
                    self.reply(f.read(), "text/html; charset=utf-8")
            elif self.path.startswith("/frame.png"):
                with app.lock:
                    frame = app.frame
                self.reply(frame, "image/png") if frame else self.reply(b"", "text/plain", 503)
            elif self.path == "/api/state":
                self.reply(json.dumps(app.state()).encode(), "application/json")
            else:
                self.reply(b"not found", "text/plain", 404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            if self.path == "/api/speech":
                if app.speech_status != "ready":
                    self.reply(json.dumps({"text": "", "sent": False, "error": f"speech model {app.speech_status}"}).encode(),
                               "application/json", 503)
                    return
                self.reply(json.dumps(app.send_speech(raw)).encode(), "application/json")
                return
            body = json.loads(raw or b"{}")
            if self.path == "/api/command" and body.get("text", "").strip():
                app.send_text(body["text"].strip()[:300])
            elif self.path == "/api/stop":
                app.send_stop()
            elif self.path == "/api/reset":
                app.reset_requested = True
            elif self.path == "/api/shutdown" and hasattr(app, "request_shutdown"):
                app.request_shutdown()  # real robot only: ends the page server, start.sh stops the rest
            else:
                self.reply(b'{"ok": false}', "application/json", 400)
                return
            self.reply(b'{"ok": true}', "application/json")

    return Handler


def main():
    app = App()

    def load_speech():
        try:
            speech.load()
            app.speech_status = "ready"
        except Exception as error:  # the page still works for typing
            app.speech_status = f"unavailable ({error})"
            print(f"Speech model could not be loaded: {error}", flush=True)
    threading.Thread(target=load_speech, daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", WEB_PORT), make_handler(app))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Open http://localhost:{WEB_PORT} in your browser. Press Ctrl+C here to stop.", flush=True)
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
