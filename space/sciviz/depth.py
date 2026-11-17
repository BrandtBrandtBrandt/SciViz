"""Pinned, Apache-2.0 Depth Anything V2 Small; one image per GPU lease."""

from __future__ import annotations

import time

MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"
REVISION = "5426e4f0f36572d16453bbda7a8389317b1bef99"


class DepthModel:
    def __init__(self, device="cuda"):
        from transformers import AutoImageProcessor, AutoModelForDepthEstimation

        if device not in ("cuda", "cpu"):
            raise ValueError("Unsupported depth device")
        self.device = device
        self.processor = AutoImageProcessor.from_pretrained(MODEL_ID, revision=REVISION, token=False, trust_remote_code=False)
        self.model = AutoModelForDepthEstimation.from_pretrained(
            MODEL_ID, revision=REVISION, token=False, trust_remote_code=False,
            use_safetensors=True,
        ).to(device).eval()

    def estimate(self, image):
        import numpy as np
        from PIL import Image
        from scipy.ndimage import grey_dilation
        import torch

        started = time.monotonic()
        # Preserve the old workflow's 0.8 nearest-neighbour input scaling.
        small = image.resize((round(image.width * .8), round(image.height * .8)), Image.Resampling.NEAREST)
        inputs = self.processor(images=small, return_tensors="pt").to(self.device)
        with torch.inference_mode():
            prediction = self.model(**inputs).predicted_depth
            depth = torch.nn.functional.interpolate(
                prediction.unsqueeze(1), size=(image.height, image.width), mode="bicubic", align_corners=False,
            )[0, 0].float().cpu().numpy()
        if not np.isfinite(depth).all() or float(np.ptp(depth)) <= 1e-6:
            raise ValueError("Depth model returned an unusable map")
        depth = (depth - depth.min()) / np.ptp(depth)
        y, x = np.mgrid[-5:6, -5:6]
        depth = grey_dilation(depth, footprint=x*x+y*y <= 25).astype(np.float32)
        return depth, {"model": MODEL_ID, "revision": REVISION, "seconds": round(time.monotonic()-started, 3)}
