from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from animation_generator import run_manim
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


@app.route("/<path:filename>")
def serve_repo_file(filename):
    return send_from_directory(str(REPO_ROOT), filename)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
