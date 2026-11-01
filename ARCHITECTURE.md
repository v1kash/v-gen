# Video Generator — Architecture

## Overview

AI-powered tool that generates a short animated video from a text prompt using **Manim** for animation and a local LLM for code generation. It can also generate single images from text prompts using **Stable Diffusion XL** running on a **CUDA GPU**.

## What it does (current capabilities)

- Accepts a text prompt via the web UI.
- Generates a Python script using Manim (defines a `Scene` class).
- Renders the script to an MP4 via the Manim CLI.
- Returns the video URL to the frontend, which plays it.
- Generates images from text prompts via Hugging Face **Stable Diffusion XL** (`diffusers`) on GPU (fp16, CUDA).
- Returns the image URL to the frontend, which displays it.
- Keeps a browsable history of past image/video generations via `GET /history`.

## What it cannot do (current limitations)

- The LLM may generate invalid or incomplete Manim code; rendering may fail.
- Only low-quality rendering (`-ql`) is used.
- Animations are simple/small — no advanced camera moves, audio, etc. are guaranteed.
- No persistence of generated videos (uses the most recent MP4 found).
- No auth, rate limiting, or error-reporting UI polish yet.

## System flow

1. User enters prompt in `frontend/index.html` / `frontend/chatbot.js`.
2. Frontend sends the prompt via `POST /generate` (video) or `POST /generate-image` (image).
3. Backend (`app/main.py`) validates prompt, calls LLM (`app/llm_model.py`) for video, or Stable Diffusion (`app/image_generator.py`) for image.
4. Video: LLM returns Manim code (fences stripped) → passed to `app/animation_generator.py`:
   - writes temp script
   - runs `manim -pql <script> <SceneName>`
   - checks return code
   - finds latest MP4 in `media/videos/`
5. Image: `app/image_generator.py` loads SDXL pipeline on CUDA (`cuda:0`, fp16 + attention slicing) → generates image → saves to `media/images/` → returns URL.
6. Backend returns JSON `{ "video_url": "/..." }` or `{ "image_url": "/..." }`.
7. Frontend sets `<video src>` / `<img src>` and plays/displays.
8. Frontend also calls `GET /history` to populate the left-side history pane.

## Components

- `frontend/` — static web UI (HTML + vanilla JS, no framework): mode toggle (image/video), combined Generate button, loading spinner + progress bar, zoom controls, history sidebar.
- `app/main.py` — Flask app: routes `/`, `/chatbot.js`, `/generate`, `/generate-image`, `/history`, catch-all static.
- `app/llm_model.py` — LLM provider layer (Ollama / LM Studio / local HF).
- `app/image_generator.py` — Stable Diffusion (diffusers) pipeline: GPU device selection, fp16, attention slicing, saves to `media/images/`.
- `app/animation_generator.py` — Manim render orchestration + video listing.
- `frontend/index.html` / `frontend/chatbot.js` — web UI logic.
- `main_animation.py` — standalone Manim scene for manual testing.

## Tech stack

- Backend: Python + Flask
- LLM: local via Ollama (default), LM Studio, or Hugging Face local
- Image generation: Stable Diffusion XL via Hugging Face `diffusers` (`StableDiffusionXLPipeline`), CUDA GPU / fp16
- Rendering: Manim Community Edition (`-pql`)

## Quick start

See `README.MD` for full run instructions (Ollama → pip install → manim → python main.py). GPU setup requires a CUDA-enabled PyTorch build (see README "GPU setup (Stable Diffusion)").
