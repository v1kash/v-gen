import gc
import os
import subprocess
import threading
import time
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import torch
from diffusers import LTXImageToVideoPipeline, LTXPipeline
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
VIDEO_OUTPUT_DIR = REPO_ROOT / "videos" / "ai_generated"
LTX_VIDEO_MODEL = os.getenv("LTX_VIDEO_MODEL", "Lightricks/LTX-Video")
VIDEO_WIDTH = 512
VIDEO_HEIGHT = 288
VIDEO_FRAME_COUNT = 33
VIDEO_FRAME_RATE = 16
VIDEO_INFERENCE_STEPS = 20

_pipeline = None
_pipeline_mode = None
_pipeline_lock = threading.Lock()


def _get_pipeline(mode: str):
    global _pipeline, _pipeline_mode

    if _pipeline is not None and _pipeline_mode != mode:
        del _pipeline
        _pipeline = None
        _pipeline_mode = None
        gc.collect()
        torch.cuda.empty_cache()

    if _pipeline is None:
        pipeline_class = LTXPipeline if mode == "text" else LTXImageToVideoPipeline
        pipeline = pipeline_class.from_pretrained(LTX_VIDEO_MODEL)
        pipeline.enable_sequential_cpu_offload()
        _pipeline = pipeline
        _pipeline_mode = mode

    return _pipeline


def _verify_h264(output_path: Path) -> bool:
    """Verify the output file is encoded with H.264 (avc1) codec."""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [ffmpeg_exe, "-i", str(output_path)],
        capture_output=True,
        text=True,
    )
    stderr = result.stderr
    # Look for the actual stream codec line (after "Input #0" and "Stream #0:0")
    # The codec line looks like: "Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661)..."
    # or: "Stream #0:0[0x1](und): Video: mpeg4 (Simple Profile) (mp4v / 0x7634706D)..."
    for line in stderr.split("\n"):
        line = line.strip()
        if line.startswith("Stream #") and "Video:" in line:
            # This is the video stream line - check the codec
            if "avc1" in line or "h264" in line.lower():
                # Make sure it's the actual codec, not just in config
                if "mpeg4" not in line.lower() and "mp4v" not in line.lower():
                    return True
            return False
    return False


def _write_web_mp4(frames, output_path: Path, fps: int) -> None:
    """Encode frames to a web-playable H.264 MP4 (``avc1``, ``yuv420p``, faststart).

    imageio's FFMPEG writer does not reliably emit the H.264/``avc1`` brand -- it
    can fall back to FFmpeg's default MPEG-4 Visual (``mp4v``) codec, which
    browsers cannot play in an HTML5 ``<video>``. We therefore drive imageio's
    bundled FFmpeg binary directly with explicit H.264 encoding flags so the
    output carries an ``avc1`` sample description and brand.
    """
    if not frames:
        raise RuntimeError("No frames to encode")

    # Ensure all frames are PIL Images in RGB mode
    pil_frames = []
    for frame in frames:
        if not isinstance(frame, Image.Image):
            raise RuntimeError(f"Expected PIL Image, got {type(frame)}")
        pil_frames.append(frame.convert("RGB"))

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    width, height = pil_frames[0].size

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{width}x{height}",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "pipe:",
        "-an",
        "-vcodec", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-preset", "medium",
        "-crf", "23",
        str(output_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for frame in pil_frames:
            proc.stdin.write(np.asarray(frame).tobytes())
    finally:
        proc.stdin.close()
    _, stderr = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            "FFmpeg H.264 encoding failed "
            f"(exit {proc.returncode}):\n{stderr.decode(errors='replace')}"
        )

    # Verify the output is actually H.264
    if not _verify_h264(output_path):
        raise RuntimeError(
            "FFmpeg encoding succeeded but output is not H.264 (avc1). "
            f"ffmpeg output: {stderr.decode(errors='replace')[:500]}"
        )


def generate_video(prompt: str, mode: str, image: Image.Image | None = None) -> str:
    if not torch.cuda.is_available():
        raise RuntimeError("Local AI video generation requires a CUDA-enabled PyTorch environment")
    if mode not in {"text", "image"}:
        raise ValueError("Video mode must be 'text' or 'image'")
    if mode == "image" and image is None:
        raise ValueError("Image-to-video requires a starting image")

    with _pipeline_lock:
        pipeline = _get_pipeline(mode)
        generation_args = {
            "prompt": prompt,
            "width": VIDEO_WIDTH,
            "height": VIDEO_HEIGHT,
            "num_frames": VIDEO_FRAME_COUNT,
            "frame_rate": VIDEO_FRAME_RATE,
            "num_inference_steps": VIDEO_INFERENCE_STEPS,
        }
        if mode == "image":
            generation_args["image"] = image.convert("RGB")

        frames = pipeline(**generation_args, output_type="pil").frames[0]
        VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = VIDEO_OUTPUT_DIR / f"ai_video_{time.time_ns()}.mp4"
        _write_web_mp4(frames, output_path, VIDEO_FRAME_RATE)

    return f"/{output_path.relative_to(REPO_ROOT).as_posix()}"


def reencode_to_h264(input_path: Path, output_path: Path | None = None, fps: int = 16) -> Path:
    """Re-encode an existing video file to web-playable H.264 MP4.
    
    Useful for fixing previously generated videos that used the wrong codec.
    """
    if output_path is None:
        output_path = input_path.with_stem(input_path.stem + "_h264")
    
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(input_path),
        "-an",
        "-vcodec", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-preset", "medium",
        "-crf", "23",
        "-r", str(fps),
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg re-encoding failed (exit {result.returncode}):\n{result.stderr}"
        )
    
    if not _verify_h264(output_path):
        raise RuntimeError("Re-encoding succeeded but output is not H.264 (avc1)")
    
    return output_path