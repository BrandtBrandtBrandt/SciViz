"""Small real compatibility checks; no models, inference services or credentials."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import time
import sys
from collections import deque

_RENDER_OUTPUTS = deque(maxlen=8)


def encoder_probe() -> dict:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return {"status": "unavailable", "reason": "ffmpeg or ffprobe is missing"}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="sciviz-encoder-") as temporary:
        output = Path(temporary) / "calibration.mp4"
        command = [
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
            "testsrc2=size=256x144:rate=24", "-t", "1", "-an",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
        ]
        subprocess.run(command, check=True, capture_output=True, timeout=20)
        completed = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(output)],
            check=True, capture_output=True, text=True, timeout=10,
        )
        metadata = json.loads(completed.stdout)
        video = [s for s in metadata["streams"] if s["codec_type"] == "video"][0]
        duration = float(metadata["format"]["duration"])
        valid = video["codec_name"] == "h264" and video["pix_fmt"] == "yuv420p" and 0.9 <= duration <= 1.1
        return {
            "status": "passed" if valid else "failed", "codec": video["codec_name"],
            "pixel_format": video["pix_fmt"], "duration_seconds": duration,
            "frames": int(video.get("nb_frames", 0)), "bytes": output.stat().st_size,
            "seconds": round(time.monotonic() - started, 3),
        }


def cpu_probe() -> dict:
    memory_bytes = None
    try:
        memory_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError):
        pass
    disk = shutil.disk_usage(tempfile.gettempdir())
    cgroup = {}
    for name in ("memory.max", "memory.current", "cpu.max"):
        path = Path("/sys/fs/cgroup") / name
        try:
            cgroup[name] = path.read_text().strip()
        except OSError:
            pass
    return {
        "scope": "environment and synthetic encoder only; not SciViz inference",
        "python": platform.python_version(), "platform": platform.system(),
        "host_cpu_count": os.cpu_count(), "host_physical_memory_bytes": memory_bytes,
        "cgroup_limits": cgroup,
        "temporary_disk_free_bytes": disk.free, "encoder": encoder_probe(),
    }


def cuda_probe(sample=None) -> dict:
    import torch

    if sample is None or sample.device.type != "cuda":
        return {"status": "not_run", "reason": "Root-level CUDA sample not enabled; no GPU verification"}
    started = time.monotonic()
    result = sample @ sample
    torch.cuda.synchronize()
    valid = bool(torch.allclose(result, torch.full_like(result, sample.shape[1])))
    return {
        "status": "passed" if valid else "failed", "torch": torch.__version__,
        "gpu": torch.cuda.get_device_name(), "cuda": torch.version.cuda,
        "vram_bytes": torch.cuda.get_device_properties(0).total_memory,
        "allocated_bytes": torch.cuda.memory_allocated(),
        "seconds": round(time.monotonic() - started, 3),
        "scope": "small matrix operation; not model memory/performance",
    }


def depthflow_probe() -> tuple[dict, str | None]:
    """CPU-only isolated renderer; synthetic input, no depth/model inference."""
    temporary = tempfile.TemporaryDirectory(prefix="sciviz-depthflow-")
    _RENDER_OUTPUTS.append(temporary)
    output = Path(temporary.name) / "calibration.mp4"
    script = Path(__file__).with_name("depthflow_probe.py")
    if not script.exists():
        script = Path(__file__).parents[1] / "depthflow" / "render.py"
    environment = dict(os.environ, HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", LP_NUM_THREADS="2", OMP_NUM_THREADS="2")
    try:
        completed = subprocess.run(
            [sys.executable, str(script), "--output", str(output)],
            capture_output=True, text=True, env=environment, timeout=45,
        )
        if completed.returncode:
            return {"status": "failed", "exit_code": completed.returncode, "detail": completed.stderr[-1200:]}, None
        line = next(line for line in reversed(completed.stdout.splitlines()) if line.startswith("SCIVIZ_RESULT="))
        result = json.loads(line.removeprefix("SCIVIZ_RESULT="))
        valid = result["frames"] == 12 and result["codec"] == "h264" and result["pixel_format"] == "yuv420p"
        return {"status": "passed" if valid else "failed", **result}, str(output) if valid else None
    except subprocess.TimeoutExpired:
        return {"status": "failed", "reason": "Synthetic CPU render exceeded 45 seconds"}, None
    except (OSError, ValueError, StopIteration, KeyError) as error:
        return {"status": "failed", "error_type": type(error).__name__}, None


def graphics_probe(backend: str = "egl") -> dict:
    import moderngl

    context = None
    resources = []
    try:
        options = {"backend": backend} if backend != "default" else {}
        context = moderngl.create_standalone_context(require=330, **options)
        program = context.program(
            vertex_shader="""#version 330
            const vec2 p[3] = vec2[](vec2(-1,-1), vec2(3,-1), vec2(-1,3));
            void main() { gl_Position = vec4(p[gl_VertexID], 0, 1); }
            """,
            fragment_shader="""#version 330
            out vec4 color;
            void main() { color = vec4(gl_FragCoord.x / 32.0, gl_FragCoord.y / 32.0, 0.25, 1); }
            """,
        )
        resources.append(program)
        vao = context.vertex_array(program, [])
        resources.append(vao)
        framebuffer = context.simple_framebuffer((32, 32), components=3)
        resources.append(framebuffer)
        framebuffer.use()
        vao.render(mode=moderngl.TRIANGLES, vertices=3)
        pixels = framebuffer.read(components=3, alignment=1)
        renderer = context.info.get("GL_RENDERER", "unknown")
        software = any(name in renderer.lower() for name in ("llvmpipe", "softpipe", "software", "swrast"))
        valid = len(pixels) == 32 * 32 * 3 and len(set(pixels)) > 8
        return {
            "status": "passed" if valid else "failed", "backend": backend,
            "renderer": renderer, "software_renderer": software,
            "version": context.info.get("GL_VERSION"), "frame_sha256": hashlib.sha256(pixels).hexdigest(),
            "scope": "synthetic GLSL frame; not DepthFlow compatibility or quality",
        }
    except Exception as error:
        return {"status": "failed", "backend": backend, "error_type": type(error).__name__, "reason": str(error)[:300]}
    finally:
        for resource in reversed(resources):
            resource.release()
        if context is not None:
            context.release()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graphics", choices=["egl", "default"])
    args = parser.parse_args()
    result = cpu_probe()
    if args.graphics:
        result["graphics"] = graphics_probe(args.graphics)
    print(json.dumps(result, indent=2))
