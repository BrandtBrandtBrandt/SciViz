"""SciViz development demo and collapsed diagnostics on the approved Free Space."""

import os
from pathlib import Path
import asyncio
import tempfile
import time

import spaces  # Import before torch so ZeroGPU can establish CUDA emulation.
import torch
import gradio as gr

from runtime_probe import cpu_probe, cuda_probe, depthflow_probe, graphics_probe

# Tiny root-level allocation follows ZeroGPU's model-placement lifecycle.
# Local runs leave this off. A missing CUDA target must never become a fake pass.
CUDA_SAMPLE = torch.ones((256, 256), device="cuda") if os.getenv("SCIVIZ_PROBE_CUDA") == "1" else None

IMAGE_GRAPH = None
IMAGE_LOAD = {"status": "not_run", "reason": "Reference image probe is not enabled"}
if os.getenv("SCIVIZ_IMAGE_PROBE") == "1":
    try:
        from image_probe import load_reference_graph
        IMAGE_GRAPH = load_reference_graph(Path("/tmp/sciviz-source"), Path(__file__).with_name("models-manifest.json"))
        IMAGE_LOAD = {"status": "ready", "checkpoint_sha256": IMAGE_GRAPH["checkpoint_sha256"], "startup_seconds": IMAGE_GRAPH["startup_seconds"]}
    except Exception as error:
        IMAGE_LOAD = {"status": "failed", "error_type": type(error).__name__, "detail": str(error)[:500]}
        print("SciViz reference loader:", IMAGE_LOAD, flush=True)

PROMPT_MODEL = None
PROMPT_LOAD = {"status": "not_run", "reason": "CPU prompt model is not enabled"}
if os.getenv("SCIVIZ_PROMPT_PROBE") == "1":
    try:
        from sciviz.prompting import PromptModel
        PROMPT_MODEL = PromptModel()
        PROMPT_LOAD = {"status": "ready", "model": PROMPT_MODEL.model_id, "device": "cpu"}
    except Exception as error:
        PROMPT_LOAD = {"status": "failed", "error_type": type(error).__name__, "detail": str(error)[:500]}
        print("SciViz CPU loader:", PROMPT_LOAD, flush=True)

DEPTH_MODEL = None
DEPTH_LOAD = {"status": "not_run"}
if os.getenv("SCIVIZ_DEPTH_PROBE") == "1":
    try:
        from sciviz.depth import DepthModel
        DEPTH_MODEL = DepthModel()
        DEPTH_LOAD = {"status": "ready"}
    except Exception as error:
        DEPTH_LOAD = {"status": "failed", "error_type": type(error).__name__, "detail": str(error)[:500]}
        print("SciViz depth loader:", DEPTH_LOAD, flush=True)


@spaces.GPU(duration=15)
def run_cuda():
    return cuda_probe(CUDA_SAMPLE)


@spaces.GPU(duration=15)
def run_graphics():
    gpu = cuda_probe(CUDA_SAMPLE)
    return {"cuda": gpu, "graphics": graphics_probe("egl")} if gpu["status"] == "passed" else {"cuda": gpu}


def image_inference(prompt=None, seed=401175538602345):
    from image_probe import generate_reference
    return generate_reference(IMAGE_GRAPH, prompt, seed) if prompt else generate_reference(IMAGE_GRAPH, seed=seed)


@spaces.GPU(duration=30)
def generate_image(prompt=None, seed=401175538602345):
    """Image-only developer diagnostic; not used by the generation pipeline."""
    return image_inference(prompt, seed)


@spaces.GPU(duration=45)
def generate_image_and_depth(prompt, seed):
    """One allocation covers both models; CPU video rendering runs afterwards."""
    image_result, image = image_inference(prompt, seed)
    depth, depth_result = DEPTH_MODEL.estimate(image)
    return image_result, image, depth, depth_result


def generate(url, abstract):
    import secrets
    yield from generate_with_seed(url, abstract, secrets.randbelow(2**53))


def generate_deterministic(url, abstract):
    yield from generate_with_seed(url, abstract, 401175538602345)


def generate_with_seed(url, abstract, seed):
    from sciviz.article import fetch_article, pasted_abstract
    from sciviz.animation import animate
    from sciviz.contracts import SciVizError

    started = time.monotonic()
    image = None
    metadata = {"api_version": 1, "seed": seed}
    try:
        if any(model is None for model in (PROMPT_MODEL, IMAGE_GRAPH, DEPTH_MODEL)):
            raise SciVizError("unavailable", "SciViz is warming up or temporarily unavailable. Please explore the existing examples.")
        if url.strip() and abstract.strip():
            raise SciVizError("choose_source", "Use an article URL or pasted abstract, rather than both.")
        yield {**metadata, "phase": "reading", "message": "Reading the article"}, None, None
        article = pasted_abstract(abstract) if abstract.strip() else asyncio.run(fetch_article(url))
        metadata.update(title=article.title, source_url=article.source_url, source_kind=article.source_kind)
        yield {**metadata, "phase": "concept", "message": "Creating a visual concept"}, None, None
        concept = PROMPT_MODEL.create(article)
        metadata.update(summary=concept["summary"], prompt=concept["prompt"], concept_seconds=concept["seconds"])
        yield {**metadata, "phase": "image", "message": "Generating the illustration and depth"}, None, None
        image_result, image, depth, depth_result = generate_image_and_depth(concept["prompt"], seed)
        metadata["image_seconds"] = image_result["generation_seconds"]
        metadata["depth_seconds"] = depth_result["seconds"]
        yield {**metadata, "phase": "animation", "message": "Animating the illustration"}, image, None
        with tempfile.TemporaryDirectory(prefix="sciviz-job-") as directory:
            renderer = Path(__file__).with_name("depthflow_probe.py")
            if not renderer.is_file():
                renderer = Path(__file__).parent.parent / "depthflow" / "render.py"
            video_path, video_result = animate(image, depth, Path(directory), renderer)
            yield {**metadata, "phase": "complete", "message": "Your visual is ready", "render": video_result,
                   "seconds": round(time.monotonic()-started, 3)}, image, video_path
    except SciVizError as error:
        yield {**metadata, "phase": "error", "code": error.code, "message": str(error)}, image, None
    except Exception as error:
        print("SciViz job failed:", type(error).__name__, flush=True)
        message = "Free generation is temporarily unavailable or its GPU quota is exhausted. Please try later or explore the existing examples."
        code = "generation_unavailable"
        if "quota" in str(error).lower() or "runs limit" in str(error).lower():
            code = "quota_exhausted"
            message = "Free GPU capacity has been used up for now. Please try later; the existing examples are always available."
        yield {**metadata, "phase": "error", "code": code, "message": message}, image, None


def run_image():
    if IMAGE_GRAPH is None:
        return IMAGE_LOAD, None
    try:
        return generate_image()
    except Exception as error:
        return {"status": "failed", "error_type": type(error).__name__, "detail": str(error)[:500]}, None


def run_prompt(url, abstract):
    from sciviz.article import fetch_article, pasted_abstract
    from sciviz.contracts import SciVizError
    if PROMPT_MODEL is None:
        return PROMPT_LOAD
    try:
        if url.strip() and abstract.strip():
            raise SciVizError("choose_source", "Use an article URL or pasted abstract, rather than both.")
        article = pasted_abstract(abstract) if abstract.strip() else asyncio.run(fetch_article(url))
        return {
            "status": "passed", "scope": "Real CPU article-to-prompt inference; no image generated",
            "article_title": article.title, "source_url": article.source_url,
            "source_kind": article.source_kind, "source_chars": len(article.text), "text_truncated": article.truncated,
            **PROMPT_MODEL.create(article),
        }
    except SciVizError as error:
        return {"status": "failed", "code": error.code, "detail": str(error)}


def pick_quanta(previous):
    from sciviz.quanta import random_article
    from sciviz.contracts import SciVizError
    try:
        return asyncio.run(random_article(previous))
    except SciVizError as error:
        return {"status": "failed", "code": error.code, "detail": str(error)}


def present_random_article(previous):
    """CPU-only URL selection; never starts the generation pipeline."""
    yield gr.update(interactive=False), "Finding a recent Quanta article…", gr.update(interactive=False), gr.update(interactive=False)
    article = pick_quanta(previous)
    if article["status"] == "ready":
        yield (gr.update(value=article["url"], interactive=True),
               f"Selected: **{article['title']}** — choose Generate visual to begin.",
               gr.update(interactive=True), gr.update(interactive=True))
    else:
        yield gr.update(interactive=True), article["detail"], gr.update(interactive=True), gr.update(interactive=True)


BIRDSONG_URL = "https://www.quantamagazine.org/what-can-birdsong-teach-us-about-human-language-20241121/"
READY = "**Ready.** Choose an article, then select Generate visual."
SPACE_CSS = """
.gradio-container { max-width: 1100px !important; margin: auto; }
#sciviz-result { align-items: center; }
#sciviz-image, #sciviz-video { width: 100%; max-width: 400px; margin-inline: auto; }
#sciviz-image img, #sciviz-video video:not(:fullscreen) { object-fit: contain; max-height: 480px; }
#sciviz-status { min-height: 52px; }
@media (max-width: 600px) {
  #sciviz-image, #sciviz-video { max-width: 100%; }
  #sciviz-image img, #sciviz-video video:not(:fullscreen) { max-height: 420px; }
}
"""


def present_generation(source, url, abstract):
    """Presentation only: retain the public /generate v1 API unchanged."""
    selected_url, selected_abstract = (url, "") if source == "url" else ("", abstract)
    for metadata, still, film in generate(selected_url, selected_abstract):
        finished = metadata["phase"] in ("complete", "error")
        prefix = "Couldn't finish: " if metadata["phase"] == "error" else ""
        yield (
            prefix + metadata["message"],
            gr.update(value=still, visible=still is not None),
            gr.update(value=film, visible=film is not None), metadata,
            gr.update(interactive=finished), gr.update(visible=not finished),
            gr.update(interactive=finished),
        )


with gr.Blocks(title="SciViz", delete_cache=(300, 1800), analytics_enabled=False) as demo:
    gr.Markdown("# SciViz\nTurn a science article into an illustration and a short 2.5D animation.")
    source = gr.State("url")
    with gr.Row(equal_height=False):
        with gr.Column(scale=5, min_width=280):
            with gr.Tabs():
                with gr.Tab("Article URL") as url_tab:
                    url = gr.Textbox(label="Article URL", value="", placeholder="https://…", max_length=2048,
                                     info="Quanta Magazine or an arXiv abstract.")
                    random_quanta = gr.Button("Choose a random Quanta article", size="sm")
                with gr.Tab("Paste an abstract") as abstract_tab:
                    abstract = gr.Textbox(label="Public abstract", lines=6, max_length=12000,
                                          placeholder="Paste an abstract here…", info="80–12,000 characters. Please don't submit confidential material.")
            with gr.Row():
                create = gr.Button("Generate visual", variant="primary", scale=3)
                stop = gr.Button("Stop waiting", visible=False, scale=1)
            status = gr.Markdown(READY, elem_id="sciviz-status")
            gr.Markdown("Free GPU capacity is limited. Generation may need to queue. "
                        "The results are artistic interpretations, not scientifically validated figures.")
        with gr.Column(scale=4, min_width=280, elem_id="sciviz-result"):
            gr.Markdown("### Your visual\nThe illustration appears first; the animation is added below when ready. "
                        "Use the player's fullscreen button for a larger view.")
            image = gr.Image(label="Illustration", type="pil", format="png", height=480,
                             interactive=False, visible=False, buttons=["download", "fullscreen"], elem_id="sciviz-image")
            video = gr.Video(label="Animation", height=480, interactive=False, visible=False,
                             autoplay=False, loop=True, buttons=["download"], elem_id="sciviz-video")
            gr.Markdown("Download anything you'd like to keep. Results are temporary.")
    with gr.Accordion("Generation details", open=False):
        details = gr.JSON(label="Source, visual concept and timings")
    with gr.Accordion("Developer checks", open=False):
        gr.Markdown("Optional diagnostics. These aren't needed to generate a visual. GPU checks use quota.")
        reference = gr.Button("Use the birdsong reference", size="sm")
        output = gr.JSON(label="Diagnostic result")
        diag_image = gr.Image(label="Diagnostic image", type="pil", format="png", height=280, interactive=False)
        diag_video = gr.Video(label="Diagnostic video", height=280, interactive=False, autoplay=False)
        for label, function, name in [
            ("Environment and encoder", cpu_probe, "probe_cpu"),
            ("ZeroGPU CUDA", run_cuda, "probe_cuda"),
            ("EGL graphics", run_graphics, "probe_graphics"),
        ]:
            gr.Button(label, size="sm").click(function, outputs=output, api_name=name, concurrency_id="probe", concurrency_limit=1)
        gr.Button("Synthetic DepthFlow render", size="sm").click(
            depthflow_probe, outputs=[output, diag_video], api_name="probe_depthflow", concurrency_id="probe", concurrency_limit=1)
        gr.Button("Fixed-prompt reference image", size="sm").click(
            run_image, outputs=[output, diag_image], api_name="probe_image", concurrency_id="probe", concurrency_limit=1)
        gr.Button("Article-to-prompt only", size="sm").click(
            run_prompt, inputs=[url, abstract], outputs=output, api_name="probe_prompt", concurrency_id="probe", concurrency_limit=1)
        gr.Button("Random Quanta article metadata", size="sm").click(
            pick_quanta, inputs=[url], outputs=output, api_name="random_article", concurrency_id="feed", concurrency_limit=1)
        # Keep the website's three-output API contract separate from UI updates.
        gr.Button(visible=False).click(generate, inputs=[url, abstract], outputs=[output, diag_image, diag_video],
                                       api_name="generate", concurrency_id="probe", concurrency_limit=1)
        gr.Button(visible=False).click(generate_deterministic, inputs=[url, abstract], outputs=[output, diag_image, diag_video],
                                       api_name="generate_reference", concurrency_id="probe", concurrency_limit=1)
    gr.Markdown("AlbedoBase XL by [albedobond](https://civitai.com/models/140737/albedobase-xl) · "
                "Qwen · Depth Anything V2 Small · ComfyUI · DepthFlow")

    url_tab.select(lambda: "url", outputs=source, queue=False, api_visibility="private")
    abstract_tab.select(lambda: "abstract", outputs=source, queue=False, api_visibility="private")
    reference.click(lambda: BIRDSONG_URL, outputs=url, queue=False, api_visibility="private")
    random_quanta.click(present_random_article, inputs=url, outputs=[url, status, create, random_quanta],
                        concurrency_id="feed", concurrency_limit=1, api_visibility="private", show_progress="minimal")
    start = create.click(lambda: (gr.update(interactive=False), gr.update(visible=True), "Waiting for free capacity…", gr.update(interactive=False)),
                         outputs=[create, stop, status, random_quanta], queue=False, api_visibility="private")
    running = start.then(present_generation, inputs=[source, url, abstract],
                         outputs=[status, image, video, details, create, stop, random_quanta],
                         concurrency_id="probe", concurrency_limit=1, api_visibility="private", show_progress="minimal")
    stop.click(lambda: (gr.update(interactive=True), gr.update(visible=False),
                        "Stopped waiting. A calculation already running may take a moment to finish.", gr.update(interactive=True)),
               outputs=[create, stop, status, random_quanta], cancels=[running], queue=False, api_visibility="private")

demo.queue(max_size=4, default_concurrency_limit=1, api_open=False)

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Monochrome(font=["Arial", "sans-serif"]), css=SPACE_CSS)
