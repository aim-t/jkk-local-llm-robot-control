#!/bin/bash
# Download the files this simulation needs but does not store in git (about 182 MB):
#   go2/     Unitree Go2 model from Google DeepMind's MuJoCo Menagerie
#   policy/  Balázs Szőnyi's Isaac Lab walking policy and its training settings (BSD-2-Clause)
#   speech_models/  Whisper base.en for speech input, from whisper.cpp (MIT), 148 MB
# Run once after cloning:  bash sim_mujoco/download_assets.sh
set -e
cd "$(dirname "$0")"
mkdir -p go2/assets policy

M=https://raw.githubusercontent.com/google-deepmind/mujoco_menagerie/main/unitree_go2
for f in go2.xml scene.xml LICENSE; do curl -sfL -o "go2/$f" "$M/$f"; done
for f in $(curl -sf "https://api.github.com/repos/google-deepmind/mujoco_menagerie/contents/unitree_go2/assets" \
           | python3 -c "import sys, json; print(' '.join(x['name'] for x in json.load(sys.stdin)))"); do
    curl -sfL -o "go2/assets/$f" "$M/assets/$f"
done

B=https://raw.githubusercontent.com/szonyibalazs/unitree_go2_IsaacSIM_correctTF/main
curl -sfL -o policy/model_7850.pt "$B/logs/rsl_rl/unitree_go2_rough/2024-04-06_02-37-07/model_7850.pt"
curl -sfL -o policy/LICENSE "$B/LICENSE"
for f in custom_rl_env.py agent_cfg.py omniverse_sim.py; do curl -sfL -o "policy/reference_$f" "$B/$f"; done
mkdir -p speech_models
[ -f speech_models/ggml-base.en.bin ] || curl -sfL -o speech_models/ggml-base.en.bin \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
echo "Downloaded: $(du -sh go2 | cut -f1) model, $(du -sh policy | cut -f1) policy"
