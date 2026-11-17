import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from sciviz.article import MAX_HTML_BYTES, extract_article, fetch_article, normalize_url, pasted_abstract
from sciviz.contracts import SciVizError


class ArticleInputTests(unittest.TestCase):
    def test_interactive_feature_is_not_treated_as_article_text(self):
        document = '<main><iframe class="full-size-interactive" src="https://www.quantamagazine.org/interactive/index.html"></iframe></main>'
        with self.assertRaises(SciVizError) as error:
            extract_article(document, "https://www.quantamagazine.org/an-interactive-feature-20261112/")
        self.assertEqual(error.exception.code, "interactive_article")

    def test_arxiv_pdf_becomes_abstract_without_fetching_pdf(self):
        self.assertEqual(normalize_url("https://arxiv.org/pdf/2406.09414.pdf?download=true#page=2"), "https://arxiv.org/abs/2406.09414")

    def test_unsafe_or_lookalike_inputs_are_rejected(self):
        for value in ["http://www.quantamagazine.org/article", "https://user:secret@arxiv.org/abs/2406.09414",
                      "https://arxiv.org:8443/abs/2406.09414", "https://127.0.0.1/article", "https://[::1]/article",
                      "https://arxiv.org.evil.example/abs/2406.09414", "https://arxiv.org/abs/2406.09414\n"]:
            with self.subTest(value=value), self.assertRaises(SciVizError):
                normalize_url(value)

    def test_pasted_abstract_is_bounded_and_has_no_fabricated_source(self):
        article = pasted_abstract("An abstract about patterns in nature and how researchers can describe them. " * 3)
        self.assertEqual(article.source_kind, "abstract")
        self.assertIsNone(article.source_url)
        with self.assertRaises(SciVizError):
            pasted_abstract("x" * 12001)


class ArticleFetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_redirect_to_internal_host_is_rejected_before_second_request(self):
        calls = []
        def respond(request):
            calls.append(str(request.url))
            return httpx.Response(302, headers={"location": "https://127.0.0.1/private"})
        with patch("sciviz.article.safehttpx.async_validate_url", new=AsyncMock(return_value="93.184.216.34")), patch(
            "sciviz.article.safehttpx.AsyncSecureTransport", return_value=httpx.MockTransport(respond)
        ):
            with self.assertRaises(SciVizError):
                await fetch_article("https://www.quantamagazine.org/test-article/")
        self.assertEqual(len(calls), 1)

    async def test_oversized_stream_is_rejected(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type": "text/html"}, content=b"x" * (MAX_HTML_BYTES + 1)))
        with patch("sciviz.article.safehttpx.async_validate_url", new=AsyncMock(return_value="93.184.216.34")), patch(
            "sciviz.article.safehttpx.AsyncSecureTransport", return_value=transport
        ):
            with self.assertRaises(SciVizError) as error:
                await fetch_article("https://www.quantamagazine.org/test-article/")
        self.assertEqual(error.exception.code, "article_too_large")

    async def test_each_redirect_host_is_validated_again(self):
        count = 0
        def respond(request):
            nonlocal count
            count += 1
            return httpx.Response(302, headers={"location": "https://arxiv.org/abs/2406.09414"}) if count == 1 else httpx.Response(403)
        resolver = AsyncMock(return_value="93.184.216.34")
        with patch("sciviz.article.safehttpx.async_validate_url", new=resolver), patch(
            "sciviz.article.safehttpx.AsyncSecureTransport", return_value=httpx.MockTransport(respond)
        ):
            with self.assertRaises(SciVizError):
                await fetch_article("https://www.quantamagazine.org/test-article/")
        self.assertEqual([call.args[0] for call in resolver.await_args_list], ["www.quantamagazine.org", "arxiv.org"])


if __name__ == "__main__":
    unittest.main()
