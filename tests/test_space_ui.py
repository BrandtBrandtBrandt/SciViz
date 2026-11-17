import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch


class SpaceUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        probes = Path(__file__).resolve().parents[1] / "space"
        sys.path.insert(0, str(probes))
        spec = importlib.util.spec_from_file_location("sciviz_space_ui", probes / "app.py")
        cls.app = importlib.util.module_from_spec(spec)
        # UI tests must never download weights or request a GPU.
        flags = {name: "0" for name in ("SCIVIZ_PROBE_CUDA", "SCIVIZ_IMAGE_PROBE", "SCIVIZ_PROMPT_PROBE", "SCIVIZ_DEPTH_PROBE")}
        with patch.dict(os.environ, flags):
            spec.loader.exec_module(cls.app)

    def test_website_generate_api_keeps_two_inputs_and_three_outputs(self):
        endpoints = self.app.demo.get_api_info()["named_endpoints"]
        self.assertEqual(len(endpoints["/generate"]["parameters"]), 2)
        self.assertEqual(len(endpoints["/generate"]["returns"]), 3)
        self.assertIn("/random_article", endpoints)
        self.assertEqual(len(endpoints["/generate_reference"]["parameters"]), 2)
        self.assertNotIn("/present_generation", endpoints)

    def test_production_seed_varies_and_reference_seed_stays_fixed(self):
        def pipeline(url, abstract, seed):
            yield seed
        with patch.object(self.app, "generate_with_seed", pipeline), patch("secrets.randbelow", side_effect=[12, 34]):
            self.assertEqual(list(self.app.generate("url", "")), [12])
            self.assertEqual(list(self.app.generate("url", "")), [34])
            self.assertEqual(list(self.app.generate_deterministic("url", "")), [401175538602345])

    def test_combined_allocation_runs_both_models_without_nested_gpu_calls(self):
        depth_model = Mock()
        depth_model.estimate.return_value = ("depth", {"seconds": 1})
        with patch.object(self.app, "image_inference", return_value=({"generation_seconds": 4}, "image")) as image, \
             patch.object(self.app, "DEPTH_MODEL", depth_model), \
             patch.object(self.app, "generate_image") as diagnostic:
            result = self.app.generate_image_and_depth("concept", 42)
        image.assert_called_once_with("concept", 42)
        depth_model.estimate.assert_called_once_with("image")
        diagnostic.assert_not_called()
        self.assertEqual(result, ({"generation_seconds": 4}, "image", "depth", {"seconds": 1}))

    def test_pipeline_uses_one_allocation_then_cpu_render_and_preserves_timings(self):
        prompt_model = Mock()
        prompt_model.create.return_value = {"summary": "summary", "prompt": "concept", "seconds": 2}
        allocation = Mock(return_value=({"generation_seconds": 4}, "image", "depth", {"seconds": 1}))
        def render(image, depth, directory, renderer):
            allocation.assert_called_once_with("concept", 42)
            self.assertEqual((image, depth), ("image", "depth"))
            return "video.mp4", {"seconds": 3}
        with patch.object(self.app, "PROMPT_MODEL", prompt_model), \
             patch.object(self.app, "IMAGE_GRAPH", object()), \
             patch.object(self.app, "DEPTH_MODEL", object()), \
             patch.object(self.app, "generate_image_and_depth", allocation), \
             patch.object(self.app, "generate_image") as diagnostic, \
             patch("sciviz.animation.animate", side_effect=render) as animate:
            results = list(self.app.generate_with_seed("", "A public science abstract. " * 8, 42))
        self.assertEqual([r[0]["phase"] for r in results], ["reading", "concept", "image", "animation", "complete"])
        self.assertEqual(results[-1][0]["image_seconds"], 4)
        self.assertEqual(results[-1][0]["depth_seconds"], 1)
        self.assertEqual(results[-1][1:], ("image", "video.mp4"))
        animate.assert_called_once()
        diagnostic.assert_not_called()

    def test_allocation_quota_failure_never_starts_render_or_publishes_partial_image(self):
        prompt_model = Mock()
        prompt_model.create.return_value = {"summary": "summary", "prompt": "concept", "seconds": 2}
        with patch.object(self.app, "PROMPT_MODEL", prompt_model), \
             patch.object(self.app, "IMAGE_GRAPH", object()), \
             patch.object(self.app, "DEPTH_MODEL", object()), \
             patch.object(self.app, "generate_image_and_depth", side_effect=RuntimeError("GPU quota exhausted")) as allocation, \
             patch("sciviz.animation.animate") as animate:
            results = list(self.app.generate_with_seed("", "A public science abstract. " * 8, 42))
        allocation.assert_called_once()
        animate.assert_not_called()
        self.assertEqual(results[-1][0]["code"], "quota_exhausted")
        self.assertEqual(results[-1][1:], (None, None))

    def test_random_picker_fills_url_without_generating(self):
        article = {"status": "ready", "url": "https://www.quantamagazine.org/example-20261103/", "title": "A science article"}
        with patch.object(self.app, "pick_quanta", return_value=article) as pick, patch.object(self.app, "generate") as generate:
            pending, ready = list(self.app.present_random_article("previous"))
        pick.assert_called_once_with("previous")
        generate.assert_not_called()
        self.assertFalse(pending[0]["interactive"])
        self.assertFalse(pending[2]["interactive"])
        self.assertEqual(ready[0]["value"], article["url"])
        self.assertIn(article["title"], ready[1])
        self.assertTrue(ready[2]["interactive"])

    def test_picker_failure_preserves_existing_url(self):
        with patch.object(self.app, "pick_quanta", return_value={"status": "failed", "detail": "Paste a URL instead."}):
            pending, failure = list(self.app.present_random_article("original"))
        self.assertNotIn("value", failure[0])
        self.assertTrue(failure[0]["interactive"])
        self.assertTrue(failure[2]["interactive"])
        self.assertTrue(failure[3]["interactive"])

    def test_abstract_tab_ignores_inactive_prefilled_url_and_completion_restores_controls(self):
        def pipeline(url, abstract):
            self.assertEqual((url, abstract), ("", "Public abstract"))
            yield {"phase": "complete", "message": "Ready"}, "image", "video.mp4"
        with patch.object(self.app, "generate", pipeline):
            result = list(self.app.present_generation("abstract", "Inactive URL", "Public abstract"))[0]
        self.assertTrue(result[1]["visible"])
        self.assertEqual(result[1]["value"], "image")
        self.assertTrue(result[2]["visible"])
        self.assertEqual(result[2]["value"], "video.mp4")
        self.assertTrue(result[4]["interactive"])
        self.assertFalse(result[5]["visible"])

    def test_animation_error_keeps_the_finished_illustration_available(self):
        def pipeline(url, abstract):
            yield {"phase": "depth", "message": "Estimating depth"}, "image", None
            yield {"phase": "error", "message": "Animation failed"}, "image", None
        with patch.object(self.app, "generate", pipeline):
            progress, failure = list(self.app.present_generation("url", "URL", ""))
        self.assertFalse(progress[4]["interactive"])
        self.assertTrue(failure[1]["visible"])
        self.assertEqual(failure[1]["value"], "image")
        self.assertFalse(failure[2]["visible"])
        self.assertTrue(failure[4]["interactive"])
