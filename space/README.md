---
title: SciViz
emoji: 🔬
colorFrom: gray
colorTo: blue
sdk: gradio
sdk_version: 6.31.0
python_version: 3.12.12
app_file: app.py
pinned: false
---

# SciViz — scientific articles, reimagined

Created by **Matias Brandt Møller**, SciViz turns a scientific article or abstract
into an illustration and a looping 2.5D animation. It explores how an automated
pipeline can give research a distinctive visual identity.

[Read the project story and try SciViz on my portfolio](https://www.matiasbrandt.com/projects/from-text-to-visuals)

## The project

I developed SciViz as an independent experiment in AI pipeline engineering,
visual prompt design and cloud deployment. The original prototype used ComfyUI
to explore the visual workflow, then Python, Truss and Baseten to serve it as a
Streamlit app.

For this interactive adaptation, I brought the pipeline to Hugging Face ZeroGPU
and replaced paid language-model API calls with an open-source model. The visual
direction draws on graphic design, retrofuturism, Art Deco and Bauhaus. The
animation uses estimated depth to create subtle parallax from a single image.

My contribution is the visual direction and the engineering that connects
article extraction, concept generation, image generation, depth estimation and
animation into one experience. The underlying models and rendering libraries
are third-party work, credited below.

## Try it

1. Paste a public article URL, choose a random Quanta Magazine article, or use
   the abstract tab to supply text directly. Submit only material you are
   comfortable sending to this public demonstration.
2. Select **Generate visual**. Phase messages show progress through article
   reading, visual concept, illustration and animation.
3. View and download both the illustration and its looping animation.

The same backend powers the demo on my portfolio. No paid API or paid hardware
fallback is used. Shared GPU capacity, per-user quotas, queues and cold starts
can cause delays or prevent a generation. Signing in to Hugging Face may provide
more quota than anonymous access; it does not guarantee availability.

These are artistic interpretations, not scientifically validated figures.
Article extraction, visual concepts and depth estimates can be imperfect.

## How it works

- **Article and concept:** bounded article extraction, followed by
  **Qwen2.5-1.5B-Instruct** on CPU to summarise the subject and create a visual
  prompt. No external language-model API is called.
- **Illustration:** **AlbedoBase XL v3.1 Large**, by albedobond, using the ComfyUI
  image workflow. Checkpoint bytes are verified against the publisher SHA-256.
- **Depth:** **Depth Anything V2 Small** estimates a depth map. Illustration and
  depth run together within one bounded ZeroGPU allocation.
- **Animation:** **DepthFlow** renders a six-second, 30 fps, 728 × 1024 H.264
  loop on CPU after GPU processing. This is depth-based parallax, not generated
  video or a reconstructed 3D scene.
- **Presentation:** Gradio serves this Space; the portfolio has its own
  integrated interface. Both retain the still image alongside the animation.

Production image seeds vary between requests. A separate deterministic
reference endpoint supports comparisons while developing the pipeline.

## API and development

The public `/generate` endpoint accepts an article URL and an abstract string
(use one source at a time), and streams three outputs: phase/result metadata,
an illustration, and an animation. `/generate_reference` has the same contract
with a fixed image seed. Collapsed diagnostics are for development; they are
not required to use the demo and may consume quota if run.

This repository contains the hosted adaptation. The original project source is
available in [SciViz on GitHub](https://github.com/BrandtBrandtBrandt/SciViz).
Dependency pins and `models-manifest.json` document the implementation; some
manifest status notes describe earlier compatibility tests.

## Credits

Created by **Matias Brandt Møller**. Original integration, visual direction and
interface work are distinct from the models and libraries used:

- [AlbedoBase XL / albedobond](https://civitai.com/models/140737/albedobase-xl)
- [Qwen2.5-1.5B-Instruct / Qwen](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct)
- [Depth Anything V2 / its authors](https://github.com/DepthAnything/Depth-Anything-V2)
- [DepthFlow / BrokenSource](https://github.com/BrokenSource/DepthFlow)
- [ComfyUI / its contributors](https://github.com/Comfy-Org/ComfyUI)
- [Gradio](https://github.com/gradio-app/gradio) and
  [Hugging Face ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu)

Linked articles belong to their respective publishers and authors. Models and
libraries retain their own licences and usage conditions; this README does not
relicense them.
