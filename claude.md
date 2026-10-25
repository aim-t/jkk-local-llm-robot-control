# JKK Internship Project

## Task (do not reword)
"The intern will investigate the use of fine-tuned open-source large language models (LLMs) in mobile robotics applications. The work will include selecting suitable models, deploying and evaluating them for robotics-related tasks, and, where feasible, running optimized models on the robot’s local computing hardware. Particular attention will be given to inference speed, resource usage, and integration with the robot’s software stack."

## Context
- Internship: JKK, Széchenyi István University, lasting one semester.
- Robot: Unitree Go2 Edu with an NVIDIA Jetson Orin Nano, 8 GB. The lab's setup guide is https://github.com/jkk-research/JKK_UNITREE_GO2: JetPack 6.2.1 (shipped with 5.1.1; no downgrade possible), ROS 2 Humble installed natively, CycloneDDS, robot computer at 192.168.123.18. The mentor said the dog uses Jazzy; which is current is not yet confirmed.
- Robot drivers in the lab repo: go2_ros2_sdk, go2_robot (has a /mode service with sit, stand_up, stand_down, stop_move, damp), unitree_ros2.
- Movement: Twist messages on `/cmd_vel`. Sit, stand up and lie down go through Unitree's Python API. The robot publishes an accurate `/odom`.
- Safety: start at 0.6 m/s and raise gradually; the maximum speed must stay an easy-to-change parameter. There is no physical emergency stop button; the robot is stopped through the API.
- Software may be installed on the Jetson after agreeing with the mentor what it is.
- Simulators available: MuJoCo or Isaac Sim. First robot tests with the mentor and Balázs Szőnyi.
- Development machine: MacBook Pro, Apple M4, 16 GB unified memory. No NVIDIA GPU, no CUDA.
- The user is a beginner in Python and LLM deployment: explain each step in plain language.

## Rules
- Ask before installing packages, downloading models, or changing anything outside this folder.
- Never delete, overwrite, move or reorganise existing files without approval.
- Show each system-changing command and say what it does before running it.

## Tools
- Models run through Ollama (GGUF format). Start it with `ollama serve`.
- Python lives in `.venv` (Python 3.12, created with `uv`). Run scripts with `.venv/bin/python`.
- Benchmark: `.venv/bin/python src/run_benchmark.py --model <name>`.

## Folders
- research/ papers and the literature spreadsheet
- data/ test commands
- src/ code
- experiments/ experiment notes and configurations
- results/ one JSON file per benchmark run; never edit these by hand
- docs/ reports

## Experiments
- Same test set, prompt, temperature 0 and seed 42 for every model.
- Record model digest, quantization, Ollama version and machine with every result.
- Tune prompts only on `data/go2_commands_dev.jsonl`; `data/go2_commands_test.jsonl` is held out for final scores.
- Report quality, latency, tokens per second, memory and file size together.

## Research
- Separate verified facts from hypotheses.
- Cite real paper titles with working links; check each link before citing.
- Do not rely on auto-generated summaries; read the paper.
