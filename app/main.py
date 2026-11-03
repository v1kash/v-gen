import json
import math
from io import BytesIO
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from PIL import Image, ImageOps, UnidentifiedImageError

from animation_generator import list_videos, run_manim
from image_generator import STYLE_PRESETS, generate_image as generate_sd_image, list_images
from llm_model import generate_code
from video_diffusion_generator import generate_video as generate_ai_video

app = Flask(__name__)

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
MAX_AI_VIDEO_UPLOAD_BYTES = 16 * 1024 * 1024
MAX_AI_VIDEO_IMAGE_PIXELS = 25_000_000


def _history_media_path(item_type, item_url):
    if item_type == "image":
        return next(
            (path for path in list_images() if f"/media/images/{path.name}" == item_url),
            None,
        )
    if item_type == "video":
        return next(
            (
                path for path in list_videos()
                if f"/{path.relative_to(REPO_ROOT).as_posix()}" == item_url
            ),
            None,
        )
    return None


def _prompt_metadata_path(media_path):
    return media_path.with_suffix(f"{media_path.suffix}.prompt.json")


def _save_media_prompt(item_type, item_url, prompt):
    media_path = _history_media_path(item_type, item_url)
    if media_path is None:
        raise RuntimeError("Generated media was not found to save its prompt")
    _prompt_metadata_path(media_path).write_text(
        json.dumps({"prompt": prompt}, ensure_ascii=False),
        encoding="utf-8",
    )


def _read_media_prompt(media_path):
    try:
        metadata = json.loads(_prompt_metadata_path(media_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    prompt = metadata.get("prompt", "") if isinstance(metadata, dict) else ""
    return prompt if isinstance(prompt, str) else ""


@app.route("/")
def index():
    return send_from_directory(str(FRONTEND_DIR), "index.html")


@app.route("/chatbot.js")
def chatbot_js():
    return send_from_directory(str(FRONTEND_DIR), "chatbot.js")


@app.route("/generate", methods=["POST"])
def generate_animation():
    try:
        prompt = (request.json or {}).get("prompt", "").strip()
        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400

        manim_code = generate_code(prompt)
        video_url = run_manim(manim_code)
        _save_media_prompt("video", video_url, prompt)

        return jsonify({"video_url": video_url})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/generate-ai-video", methods=["POST"])
def generate_local_video():
    try:
        is_multipart = request.mimetype == "multipart/form-data"
        payload = request.form if is_multipart else (request.get_json(silent=True) or {})
        prompt = payload.get("prompt", "")
        if not isinstance(prompt, str) or not prompt.strip():
            return jsonify({"error": "Prompt is required"}), 400

        mode = payload.get("mode", "text")
        if mode not in {"text", "image"}:
            return jsonify({"error": "Invalid AI video mode"}), 400

        image = None
        if mode == "image":
            uploaded_image = request.files.get("image") if is_multipart else None
            if uploaded_image is not None:
                image_bytes = uploaded_image.stream.read(MAX_AI_VIDEO_UPLOAD_BYTES + 1)
                if len(image_bytes) > MAX_AI_VIDEO_UPLOAD_BYTES:
                    return jsonify({"error": "Uploaded image must be 16 MB or smaller"}), 413
                try:
                    with Image.open(BytesIO(image_bytes)) as source:
                        if source.width * source.height > MAX_AI_VIDEO_IMAGE_PIXELS:
                            return jsonify({"error": "Uploaded image dimensions are too large"}), 400
                        image = ImageOps.exif_transpose(source).convert("RGB")
                except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
                    return jsonify({"error": "Uploaded file is not a supported image"}), 400
            else:
                image_url = payload.get("image_url")
                image_path = _history_media_path("image", image_url)
                if image_path is None:
                    return jsonify({"error": "Choose an image from history or upload one"}), 400
                with Image.open(image_path) as source:
                    image = ImageOps.exif_transpose(source).convert("RGB")

        video_url = generate_ai_video(prompt.strip(), mode=mode, image=image)
        _save_media_prompt("video", video_url, prompt.strip())
        return jsonify({"video_url": video_url})
    except Exception as exc:
        app.logger.exception("Local AI video generation failed")
        return jsonify({"error": str(exc)}), 500


@app.route("/generate-image", methods=["POST"])
def generate_image():
    try:
        payload = request.get_json(silent=True) or {}
        prompt = payload.get("prompt", "").strip()
        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400

        style = payload.get("style", "none")
        steps = payload.get("steps", 30)
        guidance_scale = payload.get("guidance_scale", 5.0)
        if not isinstance(style, str) or style not in STYLE_PRESETS:
            return jsonify({"error": "Invalid image style"}), 400
        if type(steps) is not int or not 15 <= steps <= 50:
            return jsonify({"error": "Inference steps must be an integer between 15 and 50"}), 400
        if (
            isinstance(guidance_scale, bool)
            or not isinstance(guidance_scale, (int, float))
            or not math.isfinite(guidance_scale)
            or not 2 <= guidance_scale <= 10
        ):
            return jsonify({"error": "Guidance scale must be between 2 and 10"}), 400

        image_url = generate_sd_image(
            prompt,
            style=style,
            steps=steps,
            guidance_scale=float(guidance_scale),
        )
        _save_media_prompt("image", image_url, prompt)

        return jsonify({"image_url": image_url})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/history", methods=["GET"])
def history():
    images = [
        {"type": "image", "url": f"/media/images/{p.name}", "prompt": _read_media_prompt(p)}
        for p in list_images()
    ]
    videos = [
        {
            "type": "video",
            "url": f"/{p.relative_to(REPO_ROOT).as_posix()}",
            "prompt": _read_media_prompt(p),
        }
        for p in list_videos()
    ]
    return jsonify({"images": images, "videos": videos})


@app.route("/history", methods=["DELETE"])
def delete_history_item():
    payload = request.get_json(silent=True) or {}
    item_type = payload.get("type")
    item_url = payload.get("url")

    if item_type not in ("image", "video"):
        return jsonify({"error": "Invalid media type"}), 400

    path = _history_media_path(item_type, item_url)
    if path is None or not path.is_file():
        return jsonify({"error": "Generated media not found"}), 404

    path.unlink()
    metadata_path = _prompt_metadata_path(path)
    if metadata_path.exists():
        metadata_path.unlink()
    return jsonify({"deleted": True})


@app.route("/<path:filename>")
def serve_repo_file(filename):
    return send_from_directory(str(REPO_ROOT), filename)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5000)
