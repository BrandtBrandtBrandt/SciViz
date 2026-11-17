"""Bounded CPU-only renderer subprocess, with job-local files."""

import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np

from .contracts import SciVizError


def animate(image, depth, directory: Path, renderer: Path):
    image_path, depth_path = directory / "illustration.png", directory / "depth.npy"
    image.save(image_path)
    np.save(depth_path, depth, allow_pickle=False)
    output = directory / "sciviz.mp4"
    try:
        result = subprocess.run(
            [sys.executable, str(renderer), "--output", str(output), "--image", str(image_path),
             "--depth", str(depth_path), "--width", "728", "--height", "1024", "--fps", "30",
             "--duration", "6", "--ssaa", "2"],
            env={**os.environ, "HF_HUB_OFFLINE": "1", "LP_NUM_THREADS": "8", "OMP_NUM_THREADS": "8"},
            capture_output=True, text=True, timeout=240, check=True,
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
        raise SciVizError("render_failed", "The illustration is ready, but its animation could not finish. You can still download the image.") from error
    lines = [line for line in result.stdout.splitlines() if line.startswith("SCIVIZ_RESULT=")]
    if not lines or not output.is_file():
        raise SciVizError("render_failed", "The animation did not produce a playable file.")
    metadata = json.loads(lines[-1].split("=", 1)[1])
    if metadata["frames"] != 180 or metadata["codec"] != "h264" or metadata["pixel_format"] != "yuv420p":
        raise SciVizError("render_failed", "The animation failed its output check.")
    return str(output), metadata
