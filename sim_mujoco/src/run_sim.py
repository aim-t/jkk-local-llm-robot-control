"""Run the walking Go2 in real time and accept speed commands over the network.

On a Mac, the 3D window needs MuJoCo's own launcher:
    sim_mujoco/.venv/bin/mjpython sim_mujoco/src/run_sim.py
Without a window (for automatic tests):
    sim_mujoco/.venv/bin/python sim_mujoco/src/run_sim.py --headless

ROS 2 runs in Docker, so it cannot talk to this program directly. ros_bridge_node.py runs in
the container and exchanges small UDP messages with this program on port 9870:
    container -> here:  {"vx": 0.6, "vy": 0.0, "wz": 0.0}   (the latest /cmd_vel)
    here -> container:  {"x": ..., "y": ..., "yaw": ..., "vx": ..., "wz": ...}   (becomes /odom)
If no command arrives for 0.5 s, the dog is told to stand still.
"""

import argparse
import json
import os
import socket
import time

from go2_sim import Go2Sim

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 9870
COMMAND_TIMEOUT_S = 0.5
STEP_S = 0.02  # one policy step


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true", help="no window")
    parser.add_argument("--seconds", type=float, default=0, help="stop after this long (0 = run until closed)")
    args = parser.parse_args()

    sim = Go2Sim(os.path.join(ROOT, "go2", "scene.xml"), os.path.join(ROOT, "policy", "model_7850.pt"))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    sock.setblocking(False)
    client, last_command = None, 0.0
    print(f"Go2 simulation running; waiting for speed commands on UDP port {PORT}", flush=True)

    viewer = None
    if not args.headless:
        import mujoco.viewer
        viewer = mujoco.viewer.launch_passive(sim.model, sim.data)

    start = next_step = time.monotonic()
    while viewer is None or viewer.is_running():
        now = time.monotonic()
        if args.seconds and now - start > args.seconds:
            break

        while True:  # read every command that has arrived
            try:
                packet, client = sock.recvfrom(1024)
            except BlockingIOError:
                break
            message = json.loads(packet)
            if message.get("type", "cmd_vel") != "cmd_vel":
                continue  # events for the web page (web_gui.py); not used here
            sim.command[:] = [message.get("vx", 0.0), message.get("vy", 0.0), message.get("wz", 0.0)]
            last_command = now
        if now - last_command > COMMAND_TIMEOUT_S:
            sim.command[:] = 0.0

        sim.step()
        if sim.has_fallen():
            print("The dog fell over; resetting.", flush=True)
            sim.reset()

        if client:
            x, y, yaw = sim.pose()
            body_vx, _, _ = sim.base_rotation().T @ sim.data.qvel[0:3]
            state = {"x": x, "y": y, "yaw": yaw, "vx": float(body_vx), "wz": float(sim.data.qvel[5])}
            sock.sendto(json.dumps(state).encode(), client)

        if viewer is not None:
            viewer.sync()
        next_step += STEP_S
        time.sleep(max(0.0, next_step - time.monotonic()))

    if viewer is not None:
        viewer.close()


if __name__ == "__main__":
    main()
