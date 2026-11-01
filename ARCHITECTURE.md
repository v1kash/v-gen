# Video Generator — Architecture

## Overview

AI-powered tool that generates a short animated video from a text prompt using **Manim** for animation and a local LLM for code generation.

## What it does (current capabilities)

- Accepts a text prompt via the web UI.
- Generates a Python script using Manim (defines a `Scene` class).
- Renders the script to an MP4 via the Manim CLI.
- Returns the video URL to the frontend, which plays it.

## What it cannot do (current limitations)

- The LLM may generate invalid or incomplete Manim code; rendering may fail.
- Only low-quality rendering (`-ql`) is used.
- Animations are simple/small — no advanced camera moves, audio, etc. are guaranteed.
- No persistence of generated videos (uses the most recent MP4 found).
- No auth, rate limiting, or error-reporting UI polish yet.

## System flow

1. User enters prompt in `frontend/index.html` / `frontend/chatbot.js`.
2. Frontend POSTs to backend `/generate` with `{ "prompt": ... }`.
3. Backend (`app/main.py`) validates prompt, calls LLM (`app/llm_model.py`).
4. LLM returns Manim code (fences stripped).
5. Backend passes code to `app/animation_generator.py`:
   - writes temp script
   - runs `manim -pql <script> <SceneName>`
   - checks return code
   - finds latest MP4 in `videos/`
6. Backend returns JSON `{ "video_url": "/..." }`.
7. Frontend sets `<video src>` and plays.

## Components

- `frontend/` — static web UI (HTML + vanilla JS, no framework).
- `app/main.py` — Flask app: routes `/`, `/chatbot.js`, `/generate`, catch-all static.
- `app/llm_model.py` — LLM provider layer (Ollama / LM Studio / local HF).
- `app/animation_generator.py` — Manim render orchestration.
- `main_animation.py` — standalone Manim scene for manual testing.
- `models/`, `static/`, `template/`, `videos/` — placeholders / output dirs.

## Tech stack

- Backend: Python + Flask
- LLM: local via Ollama (default), LM Studio, or Hugging Face local
- Rendering: Manim Community Edition (`-pql`)

## Quick start

See `README.MD` for full run instructions (Ollama → pip install → manim → python main.py).
