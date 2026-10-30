"""Unitree Go2 in MuJoCo, walking with Balázs Szőnyi's Isaac Lab policy (sim2sim).

The policy (policy/model_7850.pt, unitree_go2_rough) was trained in Isaac Lab. To make it walk
here, the simulator must feed it the same 235 numbers in the same order it saw in training,
and apply its output the same way. Those settings are collected below.

Taken from his repository (policy/reference_custom_rl_env.py):
    observation order, 187-point height scan (1.6 x 1.0 m grid, 0.1 m), clip (-1, 1),
    action scale 0.25 around the default pose, physics step 0.005 s, policy every 4 steps.
Taken from Isaac Lab's standard UNITREE_GO2_CFG, which his code imports (not in his repo,
so these are the most likely values, not verified):
    default joint angles, PD gains 25 / 0.5, torque limit 23.5 Nm, joint order.
"""

import math

import mujoco
import numpy as np

from load_policy import Actor

SIM_DT = 0.005
DECIMATION = 4  # policy runs every 4 physics steps = 50 Hz
ACTION_SCALE = 0.25
KP, KD, TORQUE_LIMIT = 25.0, 0.5, 23.5
HEIGHT_SCAN_POINTS = 17 * 11  # 1.6 m / 0.1 + 1 by 1.0 m / 0.1 + 1
HEIGHT_SCAN_OFFSET = 0.5

# Isaac Lab lists the Go2 joints grouped by type; the MuJoCo model lists them leg by leg.
ISAAC_JOINT_ORDER = [
    "FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint",
    "FL_thigh_joint", "FR_thigh_joint", "RL_thigh_joint", "RR_thigh_joint",
    "FL_calf_joint", "FR_calf_joint", "RL_calf_joint", "RR_calf_joint",
]


def default_angle(name):
    if "hip" in name:
        return 0.1 if name[1] == "L" else -0.1
    if "thigh" in name:
        return 0.8 if name[0] == "F" else 1.0
    return -1.5


class Go2Sim:
    def __init__(self, scene_xml, policy_path, isaac_like_joints=True):
        self.model = mujoco.MjModel.from_xml_path(scene_xml)
        self.model.opt.timestep = SIM_DT
        self.data = mujoco.MjData(self.model)
        self.actor = Actor(policy_path)

        self.qpos_idx, self.qvel_idx, self.ctrl_idx = [], [], []
        for name in ISAAC_JOINT_ORDER:
            joint = self.model.joint(name)
            self.qpos_idx.append(joint.qposadr[0])
            self.qvel_idx.append(joint.dofadr[0])
            self.ctrl_idx.append(self.model.actuator(name.replace("_joint", "")).id)
        self.default_q = np.array([default_angle(n) for n in ISAAC_JOINT_ORDER])

        if isaac_like_joints:
            # The MuJoCo model adds joint damping and friction that Isaac's PD motors do not have.
            for dof in self.qvel_idx:
                self.model.dof_damping[dof] = 0.0
                self.model.dof_frictionloss[dof] = 0.0

        self.command = np.zeros(3)  # forward m/s, sideways m/s, turn rad/s
        self.last_action = np.zeros(12)
        self.target_q = self.default_q.copy()
        self.reset()

    def reset(self):
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[2] = 0.35
        self.data.qpos[3:7] = [1, 0, 0, 0]
        self.data.qpos[self.qpos_idx] = self.default_q
        self.last_action[:] = 0
        self.target_q = self.default_q.copy()
        mujoco.mj_forward(self.model, self.data)

    def base_rotation(self):
        r = np.zeros(9)
        mujoco.mju_quat2Mat(r, self.data.qpos[3:7])
        return r.reshape(3, 3)

    def observation(self):
        rot = self.base_rotation()
        lin_vel_body = rot.T @ self.data.qvel[0:3]   # MuJoCo gives this in world axes
        ang_vel_body = self.data.qvel[3:6]           # and this already in body axes
        gravity_body = rot.T @ np.array([0.0, 0.0, -1.0])
        joint_pos = self.data.qpos[self.qpos_idx] - self.default_q
        joint_vel = self.data.qvel[self.qvel_idx]
        # Flat floor: every scan point sees the ground at height 0.
        height = np.clip(self.data.qpos[2] - HEIGHT_SCAN_OFFSET, -1.0, 1.0)
        return np.concatenate([lin_vel_body, ang_vel_body, gravity_body, self.command,
                               joint_pos, joint_vel, self.last_action,
                               np.full(HEIGHT_SCAN_POINTS, height)])

    def step(self):
        """Advance one policy step (0.02 s): decide new joint targets, then run 4 physics steps."""
        action = self.actor(self.observation())
        self.last_action = action
        self.target_q = self.default_q + ACTION_SCALE * action
        for _ in range(DECIMATION):
            q = self.data.qpos[self.qpos_idx]
            qd = self.data.qvel[self.qvel_idx]
            torque = np.clip(KP * (self.target_q - q) - KD * qd, -TORQUE_LIMIT, TORQUE_LIMIT)
            self.data.ctrl[self.ctrl_idx] = torque
            mujoco.mj_step(self.model, self.data)

    def pose(self):
        """x, y, heading (rad) of the body, as /odom would report it."""
        w, x, y, z = self.data.qpos[3:7]
        yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
        return float(self.data.qpos[0]), float(self.data.qpos[1]), yaw

    def has_fallen(self):
        upright = self.base_rotation()[2, 2]  # 1 when level, 0 when on its side
        return self.data.qpos[2] < 0.18 or upright < 0.5
