import re
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VIDEOS_DIR = REPO_ROOT / "videos"


def _scene_name(code: str) -> str:
    """Extract the Manim Scene class name from the generated code."""
    match = re.search(r"class\s+([A-Za-z_]\w*)\s*\(\s*Scene\s*\)", code)
    return match.group(1) if match else "GeneratedAnimation"


def _find_latest_video() -> Path:
    """Find the most recently created mp4 produced by Manim."""
    candidates = []
    for media_dir in (REPO_ROOT / "media", VIDEOS_DIR):
        if media_dir.is_dir():
            candidates.extend(
                p for p in media_dir.rglob("*.mp4") if "partial_movie_files" not in p.parts
            )
    if not candidates:
        raise RuntimeError("Manim did not produce a video file")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def run_manim(code: str) -> str:
    """Render the given Manim code and return the public URL of the video."""
    scene_name = _scene_name(code)

    with tempfile.TemporaryDirectory() as tmp_dir:
        script_path = Path(tmp_dir) / "generated_animation.py"
        script_path.write_text(code)

        result = subprocess.run(
            ["manim", "-pql", str(script_path), scene_name],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Manim rendering failed:\n{result.stdout}\n{result.stderr}")

    latest_video = _find_latest_video()
    return f"/{latest_video.relative_to(REPO_ROOT)}"
