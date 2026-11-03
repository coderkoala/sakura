---
name: image
description: Generate an image locally from a text prompt (no network), using stable-diffusion.cpp on the GPU
---

A local image generator is installed at `~/.local/share/sd` (stable-diffusion.cpp, Vulkan, runs on the GPU).
Model: SDXL-Turbo (`models/sd_xl_turbo_1.0_fp16.safetensors`) — fast, designed for 1-6 steps at cfg-scale 1.

To make an image, run (adjust the prompt, size and output path):

```bash
~/.local/share/sd/bin/sd-cli \
  --diffusion-model ~/.local/share/sd/models/sd_xl_turbo_1.0_fp16.safetensors \
  -p "PROMPT HERE" \
  --cfg-scale 1 --steps 5 --sampling-method euler -H 768 -W 768 \
  -o ./out.png
```

Notes:
- Turbo needs `--cfg-scale 1` and few `--steps` (4-6); higher values look worse, not better.
- If generation is slow or fails on VRAM, drop to `-H 512 -W 512`, or set `GGML_VK_VISIBLE_DEVICES=1` to force the
  discrete GPU.
- After it writes the file, confirm the path and (if asked) open it. Report the real output path, nothing invented.
- For other styles the user can drop more `.safetensors` checkpoints into `~/.local/share/sd/models/`.
