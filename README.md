# SciViz

**Scientific articles, reimagined as illustrations and looping 2.5D animations.**

I built SciViz to explore a simple idea: what if every scientific article had a visual identity that made you want to read it? The project combines article extraction, language models, a deliberately constrained visual style and depth-based animation in one pipeline.

Created by **Matias Brandt Møller**. My work covers the pipeline engineering, visual prompt design, deployment and interfaces; the underlying models and rendering libraries are credited below.

**[Try the portfolio demo](https://www.matiasbrandt.com/projects/from-text-to-visuals#sciviz-demo)** · **[Open the Hugging Face Space](https://huggingface.co/spaces/BrandtBrandtBrandt/sciviz)** · **[Read the project story](https://www.matiasbrandt.com/projects/from-text-to-visuals)**

<img src="web/public/images/ai-introspection.png" width="300" alt="A SciViz-generated illustration interpreting research into AI introspection, with a human face and golden circuitry.">

*An actual SciViz output. These are artistic interpretations, not scientifically validated figures.*

## What you can try

- Submit a Quanta Magazine article, an arXiv abstract URL, or pasted public abstract text.
- Choose a random recent Quanta article. The local revision filters multimedia features and checks that the selected article contains readable text.
- Follow progress from article reading to visual concept, illustration and animation.
- View the still image alongside a six-second looping video, with downloads and source-linked titles.

This repository now contains the Hugging Face backend and a standalone version of the browser demo. The original Streamlit/Baseten prototype is preserved under [`legacy/`](legacy/). The current demo does not call OpenAI or Baseten.

## How it works

```mermaid
flowchart LR
    A[Article or abstract] --> B[Extract bounded text]
    B --> C[Qwen on CPU: summary and visual concept]
    C --> D[AlbedoBase XL: illustration]
    D --> E[Depth Anything V2: depth]
    E --> F[DepthFlow on CPU: parallax loop]
    F --> G[Still image and video]
```

| Stage | Current implementation |
| --- | --- |
| Article reading | Bounded HTML extraction with an allowlist, redirect validation and DNS-pinned HTTP transport |
| Summary and image prompt | Qwen2.5-1.5B-Instruct on CPU |
| Illustration | AlbedoBase XL v3.1 Large, using the core ComfyUI image graph |
| Depth | Depth Anything V2 Small |
| Animation | DepthFlow, CPU rendering with EGL/Mesa, H.264 at 728 × 1024, 30 fps, six seconds |
| Interfaces | Gradio on Hugging Face; TypeScript and the Gradio client in the browser |

Illustration and depth estimation share **one bounded ZeroGPU allocation**. CPU rendering follows afterwards. The motion is parallax from an estimated depth map, rather than generative video or a recovered 3D scene.

The visual direction draws on graphic design, Swiss style, retrofuturism, Art Deco and Bauhaus. Model revisions and the checkpoint checksum are recorded in [`space/models-manifest.json`](space/models-manifest.json). Its historical compatibility notes are retained; they are not a current availability or quality guarantee.

## Repository layout

```text
space/      Self-contained Hugging Face Space: app, pipeline modules and pinned dependencies
web/        Standalone browser demo, adapted from the portfolio integration
legacy/     Original Streamlit app, OpenAI/Baseten integration and ComfyUI workflow
scripts/    Model-identity verification without downloading weights
tests/     Article-input, selection, model-identity and Space API regression checks
docs/      Source revision and file-hash provenance
```

## Run the browser demo locally

Requires Node.js 22 or newer. You do not need Python, local model weights or a GPU for this frontend.

```sh
cd web
npm ci
npm run typecheck
npm run dev
```

Open **http://127.0.0.1:4360/**. For another port, use `PORT=4361 npm run dev`.

The frontend connects directly to the existing public Space. Requests are anonymous and still use its shared capacity. **Running the frontend locally does not run the AI pipeline locally.** No Hugging Face owner token belongs in the frontend.

Loopback previews deliberately use the birdsong reference and `/generate_reference`, with a fixed image seed, to make changes easier to compare. A deployed frontend uses `/generate`, which varies the image seed, and the random article picker. The fixed seed controls image sampling; it does not guarantee identical results across hardware or dependency changes.

To build static files for another web server:

```sh
cd web
npm run build
# Publish the contents of web/dist/ through your chosen static host.
```

The frontend in this repository is a snapshot of the portfolio demo, not a live dependency of the portfolio repository. Changes must be deliberately synced between them; [`docs/source-snapshot.json`](docs/source-snapshot.json) records where this version came from.

## Backend and Hugging Face deployment

[`space/`](space/) contains the files that belong at the **root of a Gradio Space**. The root of this GitHub repository is not itself a Space deployment directory.

The backend was imported from public Space revision `899550f08780fe3dbdc5cb6439e81010cf04888d` on 17 November 2026. Follow-up changes are described in [`docs/local-changes.md`](docs/local-changes.md). The article-reading fix was published separately as revision `bbd649a17f6a59cf5b79a76517c0b245cbd45d10`; other repository changes do not automatically update the hosted Space.

For a Space configured with ZeroGPU, copy the contents of `space/` to its repository root and retain the SDK/Python versions in `space/README.md`. In the Space settings, enable the pipeline loaders with these **non-secret variables**:

```text
SCIVIZ_IMAGE_PROBE=1
SCIVIZ_PROMPT_PROBE=1
SCIVIZ_DEPTH_PROBE=1
```

The names come from the original compatibility pilot. Despite the word “PROBE”, these three flags enable the current models. `SCIVIZ_PROBE_CUDA=1` enables a separate CUDA diagnostic and is optional; diagnostic buttons are not required for normal generation.

Full inference needs the tested Linux/CUDA/ZeroGPU environment, FFmpeg and EGL/Mesa system packages from `space/packages.txt`. The Linux dependency lock is not a generic macOS installation recipe. Models and pinned ComfyUI source are downloaded at startup; model weights are not stored in this repository. Review the model licences before using another host or a different commercial setup.

Without the loader variables, the Gradio interface can run without downloading model weights, but generation reports that the models are unavailable. A UI-only run is not an inference test.

### API

The two generation endpoints take `(article_url, abstract_text)`, with exactly one source supplied, and stream `(metadata, image, video)`:

| Endpoint | Purpose |
| --- | --- |
| `/generate` | Normal generation with a fresh image seed |
| `/generate_reference` | Fixed-seed comparisons |
| `/random_article` | Select a readable recent Quanta article; no model or GPU call |

Metadata includes `api_version`, `phase`, `message`, source information and available timing data. An error may retain a completed illustration if animation fails. Output files are temporary, so download anything you want to keep. See [`web/src/app.ts`](web/src/app.ts) for the actual streaming-client integration.

## Checks

In a backend environment with the Space dependencies installed:

```sh
PYTHONPATH=space python -m unittest discover -s tests -v
```

The tests mock article-network responses and inference calls. They do not download model weights or request GPU allocations. They cover input bounds, unsafe redirects, interactive article rejection, readable random selection, model identity, API shape, shared image/depth allocation and preservation of partial results.

`python scripts/check_model_access.py` separately checks public publisher/mirror metadata. It does not download model weights; `--local-file /path/to/checkpoint` can also verify an existing checkpoint.

## Limits of the demo

The existing demo uses shared free-tier resources without a paid inference fallback. Cold starts, queues, per-user GPU quotas and rendering time can make it slow or temporarily unavailable. A signed-in Hugging Face visitor may have more quota than anonymous access, but access is not guaranteed; hosting your own ZeroGPU Space also depends on Hugging Face's eligibility rules.

Some pages are interactive features, inaccessible, or unsuitable for text extraction. Paste a public abstract if article reading fails. Small language models can miss the scientific subject, and estimated depth can produce imperfect motion around object boundaries. The result should be read as an artistic interpretation of the source, not evidence about its scientific claims. Submit only public material you are comfortable sending to the demonstration.

## Credits

- [AlbedoBase XL — albedobond](https://civitai.com/models/140737/albedobase-xl)
- [Qwen2.5-1.5B-Instruct — Qwen](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct)
- [Depth Anything V2 — its authors](https://github.com/DepthAnything/Depth-Anything-V2)
- [ComfyUI — its contributors](https://github.com/Comfy-Org/ComfyUI)
- [DepthFlow — BrokenSource](https://github.com/BrokenSource/DepthFlow)
- [Gradio](https://github.com/gradio-app/gradio) and [Hugging Face Spaces](https://huggingface.co/spaces)

Articles belong to their respective publishers and authors. Models and libraries retain their own licences and usage conditions. No model weights, API keys or private article data are included here.
