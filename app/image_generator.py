import os
import time
from pathlib import Path

import torch
from diffusers import StableDiffusionPipeline, StableDiffusionXLPipeline

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATED_DIR = REPO_ROOT / "media" / "images"
DEFAULT_SD_MODEL = os.getenv("SD_MODEL", "stabilityai/stable-diffusion-xl-base-1.0")
STYLE_PRESETS = {
    "none": "",
    "photorealistic": "photorealistic, realistic lighting, natural materials, detailed textures",
    "3d": "3D render, dimensional forms, carefully shaded materials",
    "2d": "2D illustration, clean outlines, flat colors",
    "anime": "anime style, expressive line art, cel shading",
    "sketch": "hand-drawn pencil sketch, graphite lines, textured paper",
    "painting": "traditional painting, visible brush strokes, layered pigments",
}


def list_images() -> list[Path]:
    """Return previously generated images, newest first."""
    images_dir = REPO_ROOT / "media" / "images"
    if not images_dir.is_dir():
        return []
    return sorted(images_dir.glob("generated_*.png"), key=lambda p: p.stat().st_mtime, reverse=True)

_pipe = None
_pipe_model_id = None


def _get_pipe(model_id: str):
    global _pipe, _pipe_model_id
    if _pipe is None or _pipe_model_id != model_id:
        pipe_cls = StableDiffusionXLPipeline if "xl" in model_id.lower() else StableDiffusionPipeline
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        pipe = pipe_cls.from_pretrained(model_id, torch_dtype=dtype)
        pipe = pipe.to("cuda" if torch.cuda.is_available() else "cpu")
        if torch.cuda.is_available():
            # SDXL likes extra headroom; slice attention to fit in VRAM.
            pipe.enable_attention_slicing()
        print(f"[image_generator] Using device: {pipe.device}")
        _pipe = pipe
        _pipe_model_id = model_id
    return _pipe


def generate_image(
    prompt: str,
    model_id: str | None = None,
    *,
    style: str = "none",
    steps: int = 30,
    guidance_scale: float = 5.0,
) -> str:
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is not available. Stable Diffusion requires an NVIDIA GPU. "
            "Install the CUDA-enabled PyTorch build (e.g. pip install torch --index-url https://download.pytorch.org/whl/cu121) "
            "and restart the backend. Note: the default PyPI torch build is CPU-only."
        )

    if style not in STYLE_PRESETS:
        raise ValueError("Invalid image style")
    if not 15 <= steps <= 50:
        raise ValueError("Inference steps must be between 15 and 50")
    if not 2 <= guidance_scale <= 10:
        raise ValueError("Guidance scale must be between 2 and 10")

    pipe = _get_pipe(model_id or DEFAULT_SD_MODEL)
    style_prompt = STYLE_PRESETS[style]
    styled_prompt = f"{prompt}, {style_prompt}" if style_prompt else prompt
    result = pipe(
        prompt=styled_prompt,
        num_inference_steps=steps,
        guidance_scale=guidance_scale,
    )
    image = result.images[0]
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"generated_{int(time.time())}.png"
    image.save(GENERATED_DIR / filename)
    return f"/media/images/{filename}"
