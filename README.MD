# Video Generator

AI-powered video generator that turns a text prompt into a short animated video using [Manim](https://docs.manim.community/).

## How it works

1. The frontend (`frontend/index.html`) sends a prompt to `POST /generate` or `POST /generate-image`.
2. **Video generation:** the backend (`app/main.py`) calls the LLM (`app/llm_model.py`) to generate a Manim script.
3. The script is rendered with the Manim CLI (`app/animation_generator.py`) into an MP4.
4. The frontend plays the resulting video (`/media/videos/...`).
5. **Image generation:** the backend uses a Hugging Face Stable Diffusion pipeline (`app/image_generator.py`) running on the GPU (`cuda:0`, fp16).
6. The generated image is saved to `media/images/` and served at `/media/images/...`.
7. The frontend keeps a history of past generations via `GET /history`.

## Image generation

- Uses [Hugging Face `diffusers`](https://github.com/huggingface/diffusers) `StableDiffusionXLPipeline` (or `StableDiffusionPipeline` for non-XL models).
- **Default model:** `stabilityai/stable-diffusion-xl-base-1.0` (override with the `SD_MODEL` env var).
- Runs on **CUDA GPU** in `float16` with attention slicing enabled (falls back to CPU only if no GPU is available).
- Saves output to `media/images/generated_<timestamp>.png`.
- Served to the frontend at `/media/images/generated_<timestamp>.png`.

## Setup

### GPU setup (Stable Diffusion)

Stable Diffusion (`diffusers`) needs a **CUDA-enabled PyTorch build** to run on your NVIDIA GPU. The default `pip install torch` installs a **CPU-only** build, which is why the image generation was falling back to CPU.

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

> Pick the CUDA wheel that matches your driver: `cu118`, `cu121`, or `cu124` (see https://pytorch.org/get-started/locally/). Then restart the backend so the new torch install is picked up.

### CPU-only (not recommended)

If you don't have an NVIDIA GPU, install the default CPU build:
```bash
pip install torch
```

## Install Python dependencies

```bash
pip install -r requirements.txt
```

## Running

### 1. Start Ollama (if not already running)

```bash
ollama serve
ollama pull qwen2.5-coder   # or pull whichever model you want to use
```

> If you see `Error: listen tcp 127.0.0.1:11434: bind: address already in use`, Ollama is already running — just continue.

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Make sure Manim is installed

```bash
pip install manim
```

(Manim also requires `ffmpeg` to be installed.)

### 4. Start the backend

```bash
cd app
python main.py
```

You should see:

```
 * Running on http://127.0.0.1:5000
```

### 5. Open the app

Go to **http://localhost:5000/** in your browser, enter a prompt, and click **Generate**.

## Configuration

- LLM provider — choose one:
  - `ollama` (default): uses a local Ollama instance (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`)
  - `lmstudio`: uses a local LM Studio server (`LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`)
  - `local`: uses a local Hugging Face Transformers model (`LLM_MODEL`)
- Optional model override (defaults to a small local instruct model, no token needed):
  ```
  LLM_MODEL=Qwen/Qwen2.5-0.5B-Instruct
  ```
- Optional Hugging Face token (only needed if you later switch to the Inference API):
  ```
  HF_TOKEN=hf_...
  ```

## API

### `POST /generate`

Request:
```json
{ "prompt": "A circle flying into a star" }
```

Response:
```json
{ "video_url": "/media/videos/..." }
```

### `POST /generate-image`

Request:
```json
{ "prompt": "A serene landscape" }
```

Response:
```json
{ "image_url": "/media/images/..." }
```

Generated images are saved under `media/images/` and returned with a `/media/images/...` URL.

### `GET /history`

Returns previously generated images and videos:

```json
{
  "images": [{ "type": "image", "url": "/media/images/..." }],
  "videos": [{ "type": "video", "url": "/media/videos/..." }]
}
```

## Render command

The backend renders via:

```bash
manim -pql <script.py> <SceneName>
```
