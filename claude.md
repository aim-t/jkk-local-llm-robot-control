# JKK Internship Project

## Task (do not reword)
"The intern will investigate the use of fine-tuned open-source large language models (LLMs) in mobile robotics applications. The work will include selecting suitable models, deploying and evaluating them for robotics-related tasks, and, where feasible, running optimized models on the robot’s local computing hardware. Particular attention will be given to inference speed, resource usage, and integration with the robot’s software stack."

## Context
- Internship: JKK, Széchenyi István University, lasting one semester.
- Robot: Unitree Go2 Edu with an NVIDIA Jetson Orin Nano (memory size not yet confirmed). The robot runs ROS 2 Jazzy; the lab uses Humble and Jazzy. Movement is commanded with Twist messages on `/cmd_vel`. Confirmed by the mentor on 12 Oct 2026.
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
