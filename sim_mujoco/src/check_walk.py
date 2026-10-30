"""Headless check: does the dog stand, walk forward, turn, and stop without falling?"""
import math, sys
import numpy as np
from go2_sim import Go2Sim
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run(isaac_like):
    sim = Go2Sim(ROOT + "/go2/scene.xml", ROOT + "/policy/model_7850.pt", isaac_like_joints=isaac_like)
    plan = [("stand", (0, 0, 0), 2.0), ("forward 0.6 m/s", (0.6, 0, 0), 5.0),
            ("turn left 0.5 rad/s", (0, 0, 0.5), 4.0), ("backward 0.3 m/s", (-0.3, 0, 0), 3.0), ("stand", (0, 0, 0), 2.0)]
    print(f"--- isaac_like_joints={isaac_like} ---")
    for label, cmd, seconds in plan:
        sim.command[:] = cmd
        x0, y0, yaw0 = sim.pose(); heights = []
        for _ in range(int(seconds / 0.02)):
            sim.step(); heights.append(sim.data.qpos[2])
            if sim.has_fallen():
                print(f"  {label:<22} FELL after {len(heights)*0.02:.1f} s"); return
        x, y, yaw = sim.pose()
        dist = math.hypot(x - x0, y - y0); fwd = (x - x0) * math.cos(yaw0) + (y - y0) * math.sin(yaw0)
        turn = math.degrees(math.atan2(math.sin(yaw - yaw0), math.cos(yaw - yaw0)))
        print(f"  {label:<22} {seconds:.0f} s: forward {fwd:+.2f} m (speed {fwd/seconds:+.2f} m/s), turned {turn:+6.1f} deg, body height {np.mean(heights):.2f} m")

run(True); run(False)
