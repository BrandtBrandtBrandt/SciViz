"""Render real DepthFlow with synthetic input/depth; no AI model downloads.

This tests the library's current orbital preset, not visual equivalence with
the old ComfyUI preset. Use the isolated render environment, not the probe app.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time

import numpy as np
from depthflow.examples.presets import Orbital
from shaderflow.ffmpeg import FFmpegVideoCodecH264


def render(output: Path, width=256, height=256, fps=12, duration=1.0, ssaa=1.0, image_path=None, depth_path=None) -> dict:
    if output.exists():
        raise ValueError("Refusing to overwrite an existing result")
    output.parent.mkdir(parents=True, exist_ok=True)
    y, x = np.mgrid[0:256, 0:256]
    circle = (x - 128) ** 2 + (y - 128) ** 2 < 65 ** 2
    image = np.stack((x, y, np.full_like(x, 80)), axis=-1).astype(np.uint8)
    image[circle] = [240, 160, 60]
    depth = np.where(circle, 0.8, 0.2).astype(np.float32)
    if image_path is not None:
        from PIL import Image
        image = np.array(Image.open(image_path).convert("RGB"))
        depth = np.load(depth_path, allow_pickle=False)
        if depth.shape != image.shape[:2] or not np.isfinite(depth).all():
            raise ValueError("Image/depth dimensions or values differ")
    started = time.monotonic()
    scene = Orbital(backend="headless", width=width, height=height)
    # Match the original workflow explicitly instead of inheriting CRF 20.
    scene.ffmpeg.vcodec = FFmpegVideoCodecH264(crf=11)
    try:
        scene.input(image=image, depth=depth)
        renderer = scene.opengl.info.get("GL_RENDERER", "unknown")
        scene.main(width=width, height=height, fps=fps, time=duration, ssaa=ssaa, quality=100, output=output, turbo=False)
    finally:
        if scene.window is not None:
            scene.window.destroy()
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(output)],
        check=True, capture_output=True, text=True, timeout=10,
    )
    metadata = json.loads(completed.stdout)
    stream = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    return {
        "scope": "real DepthFlow 1.0.1; modern orbital preset",
        "input": "provided RGB and estimated depth" if image_path else "synthetic calibration",
        "models_downloaded": False, "renderer": renderer,
        "ssaa": ssaa,
        "encoding_crf": 11,
        "width": stream["width"], "height": stream["height"], "codec": stream["codec_name"],
        "pixel_format": stream["pix_fmt"], "frames": int(stream.get("nb_frames", 0)),
        "duration_seconds": float(metadata["format"]["duration"]),
        "render_seconds": round(time.monotonic() - started, 3), "bytes": output.stat().st_size,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=256)
    parser.add_argument("--height", type=int, default=256)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--duration", type=float, default=1)
    parser.add_argument("--ssaa", type=float, default=1)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--depth", type=Path)
    arguments = parser.parse_args()
    if not (64 <= arguments.width <= 1024 and 64 <= arguments.height <= 1024
            and 1 <= arguments.fps <= 30 and 0 < arguments.duration <= 6 and 1 <= arguments.ssaa <= 2):
        parser.error("Probe dimensions or duration outside bounded test limits")
    if bool(arguments.image) != bool(arguments.depth):
        parser.error("Both image and depth are required")
    result = render(arguments.output.resolve(), arguments.width, arguments.height, arguments.fps, arguments.duration, arguments.ssaa, arguments.image, arguments.depth)
    print("SCIVIZ_RESULT=" + json.dumps(result))
