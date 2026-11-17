import unittest
import time
from unittest.mock import AsyncMock, patch

from sciviz.contracts import SciVizError
from sciviz.quanta import MAX_FEED_BYTES, choose_article, parse_feed
import sciviz.quanta as quanta


class QuantaFeedTests(unittest.TestCase):
    def test_multimedia_items_do_not_enter_the_article_pool(self):
        feed = b'<rss><channel><item><title>Interactive feature</title><link>https://www.quantamagazine.org/interactive-20261112/</link><category>Multimedia</category></item><item><title>A readable article</title><link>https://www.quantamagazine.org/readable-20261110/</link><category>Biology</category></item></channel></rss>'
        self.assertEqual([item["title"] for item in parse_feed(feed)], ["A readable article"])

    def test_only_real_quanta_article_links_are_selected_and_deduplicated(self):
        links = ["https://www.quantamagazine.org/a-science-story-20261102/",
                 "https://www.quantamagazine.org/a-science-story-20261102/",
                 "https://www.quantamagazine.org/category/physics/",
                 "https://evil.example/science-20261102/",
                 "https://arxiv.org/abs/2406.09414"]
        feed = '<rss><channel>' + ''.join(f'<item><title>Science &amp; Nature</title><link>{url}</link></item>' for url in links) + '</channel></rss>'
        self.assertEqual(parse_feed(feed.encode()), [{"title": "Science & Nature", "url": links[0]}])

    def test_repeat_is_avoided_when_another_article_exists(self):
        articles = [{"url": "a"}, {"url": "b"}]
        self.assertEqual(choose_article(articles, "a"), {"url": "b"})
        self.assertEqual(choose_article(articles[:1], "a"), {"url": "a"})

    def test_oversized_feed_and_entity_declarations_are_rejected(self):
        for data in (b"x" * (MAX_FEED_BYTES+1), b'<!DOCTYPE rss [<!ENTITY x "expand">]><rss/>'):
            with self.assertRaises(ValueError):
                parse_feed(data)


class ReadablePickerTests(unittest.IsolatedAsyncioTestCase):
    async def test_unreadable_candidate_is_skipped_before_returning_a_link(self):
        articles = [{"url": "bad", "title": "Interactive"}, {"url": "good", "title": "Article"}]
        with patch.object(quanta, "_cached_articles", articles), patch.object(quanta, "_expires_at", time.monotonic()+100), \
             patch.object(quanta, "choose_article", side_effect=lambda pool, previous: pool[0]), \
             patch.object(quanta, "fetch_article", new=AsyncMock(side_effect=[SciVizError("interactive_article", "Interactive"), object()])) as read:
            result = await quanta.random_article()
        self.assertEqual(result["url"], "good")
        self.assertEqual(read.await_count, 2)

    async def test_unreadable_checks_are_bounded_and_fail_with_guidance(self):
        articles = [{"url": str(i), "title": "Unavailable"} for i in range(5)]
        with patch.object(quanta, "_cached_articles", articles), patch.object(quanta, "_expires_at", time.monotonic()+100), \
             patch.object(quanta, "choose_article", side_effect=lambda pool, previous: pool[0]), \
             patch.object(quanta, "fetch_article", new=AsyncMock(side_effect=SciVizError("unreadable_article", "No article"))) as read:
            with self.assertRaises(SciVizError) as error:
                await quanta.random_article()
        self.assertEqual(read.await_count, 3)
        self.assertEqual(error.exception.code, "feed_unavailable")
