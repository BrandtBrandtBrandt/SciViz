"""Minimal original ComfyUI image graph, loaded once at Space startup.

The public diagnostic uses a fixed prompt and the original reference settings.
No persistent ComfyUI server or custom nodes are started. Model bytes are
accepted only after verification against the publisher's recorded SHA-256.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import time
import urllib.request

COMFY_REVISION = "3aaabb12d422eb35cd0314a09582c0a47d505a37"
PROMPT = (
    "A songbird surrounded by geometric sound waves, a visual exploration of birdsong and language. "
    "Graphic design, swiss style, retro futurism, art deco, bauhaus, modern."
)


def prepare_source(cache: Path) -> Path:
    source = cache / f"ComfyUI-{COMFY_REVISION}"
    if (source / "nodes.py").is_file():
        return source
    cache.mkdir(parents=True, exist_ok=True)
    url = f"https://codeload.github.com/comfyanonymous/ComfyUI/tar.gz/{COMFY_REVISION}"
    with urllib.request.urlopen(url, timeout=40) as response:
        data = response.read(32 * 1024 * 1024 + 1)
    if len(data) > 32 * 1024 * 1024:
        raise ValueError("Pinned ComfyUI source exceeds the archive limit")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive.getmembers():
            parts = Path(member.name).parts
            if (not parts or parts[0] != source.name or ".." in parts
                    or not (member.isfile() or member.isdir())):
                raise ValueError("Unexpected entry in pinned ComfyUI source")
        archive.extractall(cache, filter="data")
    return source


def load_reference_graph(cache: Path, manifest_path: Path) -> dict:
    # Called from the app's root module, after importing spaces and torch.
    import torch
    from huggingface_hub import hf_hub_download

    started = time.monotonic()
    model = json.loads(manifest_path.read_text())["models"][0]
    mirror = model["mirror"]
    checkpoint = Path(hf_hub_download(
        repo_id=mirror["repo"], filename=mirror["filename"],
        revision=mirror["revision"], token=False,
    ))
    if checkpoint.stat().st_size != model["size_bytes"]:
        raise ValueError("Checkpoint size differs from the publisher manifest")
    with checkpoint.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != model["sha256"]:
        raise ValueError("Checkpoint failed publisher SHA-256 verification")

    source = prepare_source(cache)
    sys.path.insert(0, str(source))
    from comfy.cli_args import args
    args.disable_smart_memory = True
    args.highvram = True
    import folder_paths
    import nodes

    folder_paths.add_model_folder_path("checkpoints", str(checkpoint.parent))
    diffusion, clip, vae = nodes.CheckpointLoaderSimple().load_checkpoint(checkpoint.name)
    # ZeroGPU emulates CUDA at startup and makes it real during the GPU lease.
    diffusion.model.to("cuda")
    clip.cond_stage_model.to("cuda")
    vae.first_stage_model.to("cuda")
    return {
        "diffusion": diffusion, "clip": clip, "vae": vae, "nodes": nodes,
        "checkpoint_sha256": digest, "startup_seconds": round(time.monotonic() - started, 3),
        "torch": torch.__version__,
    }


def generate_reference(graph: dict, prompt: str = PROMPT, seed: int = 401175538602345) -> tuple[dict, object]:
    import numpy as np
    from PIL import Image
    import torch

    if not isinstance(prompt, str) or not 20 <= len(prompt) <= 1600:
        raise ValueError("Image prompt outside bounded limits")
    if not isinstance(seed, int) or not 0 <= seed < 2**53:
        raise ValueError("Seed outside JavaScript-safe integer range")
    started = time.monotonic()
    nodes = graph["nodes"]
    with torch.inference_mode():
        positive = nodes.CLIPTextEncode().encode(graph["clip"], prompt)[0]
        negative = nodes.CLIPTextEncode().encode(graph["clip"], "text, watermark")[0]
        latent = nodes.EmptyLatentImage().generate(728, 1024, 1)[0]
        samples = nodes.KSampler().sample(
            graph["diffusion"], seed, 20, 8, "euler", "normal", positive, negative, latent, denoise=1,
        )[0]
        pixels = nodes.VAEDecode().decode(graph["vae"], samples)[0][0].detach().cpu().numpy()
    if not np.isfinite(pixels).all():
        raise ValueError("Reference image contains non-finite pixels")
    image = Image.fromarray(np.clip(pixels * 255, 0, 255).astype(np.uint8))
    return {
        "status": "passed", "scope": "Original ComfyUI image subgraph; fixed diagnostic prompt",
        "comfy_revision": COMFY_REVISION, "checkpoint_sha256": graph["checkpoint_sha256"],
        "width": image.width, "height": image.height, "steps": 20, "cfg": 8,
        "seed": seed, "sampler": "euler", "scheduler": "normal", "prompt": prompt,
        "startup_seconds": graph["startup_seconds"],
        "generation_seconds": round(time.monotonic() - started, 3),
        "vram_allocated_bytes": torch.cuda.memory_allocated(),
    }, image
