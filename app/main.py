from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from animation_generator import list_videos, run_manim
from image_generator import generate_image as generate_sd_image, list_images
from llm_model import generate_code

app = Flask(__name__)

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
FRONTEND_DIR = REPO_ROOT / "frontend"


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

        return jsonify({"video_url": video_url})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/generate-image", methods=["POST"])
def generate_image():
    try:
        prompt = (request.json or {}).get("prompt", "").strip()
        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400

        image_url = generate_sd_image(prompt)

        return jsonify({"image_url": image_url})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/history", methods=["GET"])
def history():
    images = [
        {"type": "image", "url": f"/media/images/{p.name}"}
        for p in list_images()
    ]
    videos = [
        {"type": "video", "url": f"/{p.relative_to(REPO_ROOT)}"}
        for p in list_videos()
    ]
    return jsonify({"images": images, "videos": videos})


@app.route("/<path:filename>")
def serve_repo_file(filename):
    return send_from_directory(str(REPO_ROOT), filename)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
