# Video Generator

AI-powered video generator that turns a text prompt into a short animated video using [Manim](https://docs.manim.community/).

## How it works

1. The frontend (`frontend/index.html`) sends a prompt to `POST /generate`.
2. The backend (`app/main.py`) calls the LLM (`app/llm_model.py`) to generate a Manim script.
3. The script is rendered with the Manim CLI (`app/animation_generator.py`) into an MP4.
4. The frontend plays the resulting video.

## Setup

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

## Render command

The backend renders via:

```bash
manim -pql <script.py> <SceneName>
```
