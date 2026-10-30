# Go2 MuJoCo simulation

A walking Unitree Go2 in MuJoCo on the Mac, driven by the project's ROS 2 nodes through `/cmd_vel` and `/odom`, like the real robot.

Everything for the simulation lives in this folder, including its own Python in `.venv`. Deleting the folder removes it completely; nothing else in the project depends on it.

## Where the parts come from

| Part | Source | Licence |
|---|---|---|
| Go2 body model (`go2/`) | [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie/tree/main/unitree_go2), Google DeepMind | `go2/LICENSE` |
| Walking policy (`policy/model_7850.pt`) | [unitree_go2_IsaacSIM_correctTF](https://github.com/szonyibalazs/unitree_go2_IsaacSIM_correctTF), Balázs Szőnyi, trained in Isaac Lab (`unitree_go2_rough`) | BSD-2-Clause, `policy/LICENSE` |
| `policy/reference_*.py` | Copies of his training settings, kept for reference | BSD-2-Clause |

The policy was trained in Isaac Lab and is reused here without retraining ("sim2sim"). `src/go2_sim.py` gives it the same 235 inputs it saw in training. The default joint angles, motor gains and joint order are Isaac Lab's standard Go2 values, which his code imports; they are not in his repository and have not been confirmed with him.

## Files

| File | Job |
|---|---|
| `src/load_policy.py` | Reads the policy file with numpy, so PyTorch is not needed |
| `src/go2_sim.py` | The simulated dog and the policy |
| `src/run_sim.py` | Runs the simulation in real time, with or without a window, and exchanges speed and position with ROS 2 over UDP port 9870 |
| `src/ros_bridge_node.py` | Runs in the ROS 2 container: `/cmd_vel` to the simulation, simulation to `/odom` |
| `src/web_gui.py`, `web/index.html` | The web console: simulation, camera picture and results page on http://localhost:8765 |
| `src/speech.py` | Speech to text with a local Whisper model (whisper.cpp through pywhispercpp) |
| `start_gui.sh` | Starts everything for the web console with one command |
| `src/check_walk.py` | Quick test without a window or ROS 2: stand, walk, turn, walk back |

## Setup (already done on this Mac)

```bash
bash sim_mujoco/download_assets.sh   # the Go2 model and the policy; not stored in git
uv venv sim_mujoco/.venv --python 3.12
uv pip install --python sim_mujoco/.venv/bin/python mujoco==3.17.0 pywhispercpp==1.5.1
ln -s ~/.local/share/uv/python/cpython-3.12.10-macos-aarch64-none/lib/libpython3.12.dylib sim_mujoco/.venv/lib/libpython3.12.dylib
```

The last line lets MuJoCo's window launcher (`mjpython`) find the Python library that `uv` installs elsewhere. Without it the window fails to open.

## Run it

All commands start in the project folder. You need three terminals and Docker Desktop running.

**Terminal 1, the simulation with a 3D window:**

```bash
sim_mujoco/.venv/bin/mjpython sim_mujoco/src/run_sim.py
```

Close the window to stop it. Use `.venv/bin/python ... --headless` instead for no window.

**Terminal 2, the ROS 2 container with the bridge:**

```bash
docker run --rm -it --name go2_sim -v "$PWD":/ws:ro ros:jazzy-ros-base \
  python3 /ws/sim_mujoco/src/ros_bridge_node.py
```

**Terminal 3, the movement node and commands, in the same container:**

```bash
docker exec -it go2_sim bash
source /opt/ros/jazzy/setup.bash
cd /ws/src
python3 cmd_vel_node.py --ros-args -p max_angular_speed:=1.0 &
python3 send.py move 1.0
python3 send.py turn 90
python3 send.py stop
```

To give plain-language commands as well, start `ollama serve` on the Mac and run `go2_command_node.py` in the container, as in the main README, then `python3 send.py text "Walk forward one metre."`.

## Web console (easiest)

One command starts everything: Docker Desktop if it is closed, the language model, the ROS 2 container with all nodes, and the simulation. A browser page opens at http://localhost:8765.

```bash
bash sim_mujoco/start_gui.sh
```

On the page you can type a command or click an example, and press STOP (stops at once, without the model) or Reset dog. It shows:

- the live camera view and the path seen from above;
- live speed and turn rate against what was asked, heading, position, body height and falls;
- for every command: what the model understood, how long it took, the target, what the dog actually achieved, the error, and whether it worked.

**Two ways to give commands**, switched with the Type and Speak tabs:

- **Type:** write a sentence and press Send, or click an example.
- **Speak:** hold the "Hold to talk" button (or the space bar), say the command, and let go. A local Whisper model (`speech_models/ggml-base.en.bin`, English) turns it into text on the Mac, with no internet, and the text then goes through the same model, safety check and nodes as typed text. Saying just "stop" skips the language model and stops at once. The first time, the browser asks for microphone permission.

The history table shows how each command was given, and for spoken ones how long recognition took.

A move counts as "Worked" within 10 cm or 10 % of the target, a turn within 10 degrees or 10 %. These tolerances are the page's own choice. Press Ctrl+C in the terminal to stop everything; the script removes the container and stops the language model if it started it.

## Talk to the dog in plain language

Four terminals, all started in the project folder, with Docker Desktop running.

**Terminal 1, the language model:**

```bash
ollama serve
```

**Terminal 2, the simulation window:**

```bash
sim_mujoco/.venv/bin/mjpython sim_mujoco/src/run_sim.py
```

**Terminal 3, the ROS 2 container with the bridge:**

```bash
docker run --rm -it --name go2_sim -v "$PWD":/ws:ro \
  -e OLLAMA_URL=http://host.docker.internal:11434 \
  ros:jazzy-ros-base python3 /ws/sim_mujoco/src/ros_bridge_node.py
```

**Terminal 4, the two project nodes and the chat:**

```bash
docker exec -it go2_sim bash
source /opt/ros/jazzy/setup.bash
cd /ws/src
python3 cmd_vel_node.py --ros-args -p max_angular_speed:=1.0 > /tmp/cmd_vel.log 2>&1 &
OLLAMA_URL=http://host.docker.internal:11434 python3 go2_command_node.py > /tmp/language.log 2>&1 &
sleep 10
python3 chat.py
```

Then type, for example:

```text
you> Walk forward one metre.
dog> walk forward 1 m  (0.7 s)
you> Turn left 45 degrees.
dog> turn left 45 degrees  (0.7 s)
you> Make me a cup of coffee.
dog> refused: model did not recognise a command the robot can do  (0.9 s)
```

An empty line or `stop` stops the dog at once, without waiting for the model. `quit` leaves the chat. To stop everything: `quit`, then Ctrl+C in terminals 3, 2 and 1.

## Test results (28 October 2026)

Without ROS 2 (`check_walk.py`):

| Command | Result |
|---|---|
| Stand, 2 s | stayed upright, drifted 0.02 m |
| Forward 0.6 m/s, 5 s | walked 2.57 m (0.51 m/s) |
| Turn left 0.5 rad/s, 4 s | turned 31 degrees (about 0.14 rad/s) |
| Backward 0.3 m/s, 3 s | walked 0.57 m (0.19 m/s) |

Through ROS 2 (`cmd_vel_node.py` with `max_angular_speed:=1.0`):

| Command | Result |
|---|---|
| move 1.0 | stopped at 1.00 m, measured by `/odom` |
| turn 90 | 79 degrees, then the time limit stopped it |
| move -0.5 | 0.44 m, then the time limit stopped it |
| move 3.0, stop after 2 s | stopped |

The dog did not fall in any test.

## Known limits

- **Turning is slow.** The policy turns at about a third of the commanded rate, so turns and backward moves often hit `cmd_vel_node.py`'s time limit before finishing. The likely cause is a mismatch in joint settings or friction between Isaac Lab and MuJoCo. Raising `max_angular_speed` helps.
- **The body stands higher than expected** (0.39 m), which suggests the default pose or motor gains differ slightly from training.
- **Flat floor only.** The 187-point height scan is filled with flat-floor values.
- **Sit, stand up and lie down** are not simulated.
- **This is not the lab's simulator.** Results here are a pipeline check on a laptop. They are not evidence of how the real Go2 or Balázs's Isaac Sim setup behaves.

## Remove it

```bash
rm -rf sim_mujoco
```
