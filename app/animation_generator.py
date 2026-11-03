import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VIDEOS_DIR = REPO_ROOT / "videos"


def _manim_command() -> list[str]:
    """Return the command used to invoke Manim.

    ``pip install --user`` places the ``manim`` script in ``~/.local/bin``,
    which is often not on PATH (especially when the server is launched from a
    different shell). Prefer an executable we can find, then fall back to
    ``python -m manim`` so the CLI works without PATH changes.
    """
    exe = shutil.which("manim")
    if exe:
        return [exe]

    # Console scripts next to the running interpreter (virtualenvs, pipx, etc.).
    for candidate in (
        Path(sys.executable).parent / "manim",
        Path.home() / ".local" / "bin" / "manim",
    ):
        if candidate.is_file():
            return [str(candidate)]

    # Last resort: run Manim as a module from the same interpreter.
    return [sys.executable, "-m", "manim"]


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


def list_videos() -> list[Path]:
    """Return all mp4 files found in the media directories, newest first."""
    found = []
    for media_dir in (REPO_ROOT / "media", VIDEOS_DIR):
        if media_dir.is_dir():
            found.extend(
                p for p in media_dir.rglob("*.mp4") if "partial_movie_files" not in p.parts
            )
    return sorted(set(found), key=lambda p: p.stat().st_mtime, reverse=True)


def run_manim(code: str) -> str:
    """Render the given Manim code and return the public URL of the video."""
    scene_name = _scene_name(code)

    with tempfile.TemporaryDirectory() as tmp_dir:
        script_path = Path(tmp_dir) / "generated_animation.py"
        script_path.write_text(code)

        try:
            result = subprocess.run(
                [*_manim_command(), "-pql", str(script_path), scene_name],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Manim is not installed or not on PATH. Install it with "
                "'pip install manim' (see requirements.txt) and make sure the "
                "'manim' executable is available in the same environment that "
                "runs this server."
            ) from exc
        if result.returncode != 0:
            raise RuntimeError(f"Manim rendering failed:\n{result.stdout}\n{result.stderr}")

    latest_video = _find_latest_video()
    return f"/{latest_video.relative_to(REPO_ROOT)}"
