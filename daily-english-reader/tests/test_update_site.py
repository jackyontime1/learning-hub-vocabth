import json
import base64
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import update_site as site


class FakeResponse:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload or {}
        self.text = text
        self.content = text.encode("utf-8")

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise site.requests.HTTPError(str(self.status_code))


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)

    def get(self, *args, **kwargs):
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def post(self, *args, **kwargs):
        return self.get(*args, **kwargs)


class DailyReaderTests(unittest.TestCase):
    def test_demo_stories_have_unique_topic_images(self):
        titles = [row[1] for row in site.DEMO_TOPICS]
        images = [site.DEMO_IMAGE_MAP[title] for title in titles]
        self.assertEqual(len(images), 6)
        self.assertEqual(len(set(images)), 6)

    def test_local_image_generator_is_cached(self):
        article = site.demo_articles()[0]
        payload = {"images": [base64.b64encode(b"x" * 10_001).decode("ascii")]}
        config = {
            "demo": False,
            "local_image_url": "http://127.0.0.1:7860",
            "local_image_steps": 12,
            "local_image_timeout": 60,
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(site, "STATIC_DIR", root / "static"), \
                 patch.object(site, "IMAGE_CACHE_PATH", root / "images.json"):
                result = site.image_for(article, FakeSession([FakeResponse(200, payload)]), object(), config)
                self.assertTrue((root / "static" / "images" / result["local_filename"]).exists())
                self.assertEqual(result["credit"], "Generated locally with Stable Diffusion")

    def test_free_only_cannot_be_disabled(self):
        with patch.dict(site.os.environ, {"FREE_ONLY": "0"}, clear=False):
            with self.assertRaises(RuntimeError):
                site.config_from_env()

    def test_daily_selection_has_two_per_level(self):
        candidates = site.demo_articles()
        selected = site.choose_daily_articles(candidates)
        self.assertEqual(len(selected), site.DAILY_ARTICLE_COUNT)
        self.assertEqual({level: sum(row["level"] == level for row in selected) for level in site.LEVELS},
                         {level: site.TARGET_PER_LEVEL for level in site.LEVELS})

    def test_word_spans_wrap_every_english_word(self):
        markup = str(site.word_spans("Clean energy works.", {
            "clean": "สะอาด", "energy": "พลังงาน", "works": "ทำงาน",
        }))
        self.assertEqual(markup.count('class="word"'), 3)
        self.assertIn("พลังงาน", markup)

    def test_word_spans_include_part_of_speech(self):
        markup = str(site.word_spans("Clean energy works.", {
            "clean": "สะอาด", "energy": "พลังงาน", "works": "ทำงาน",
        }))
        self.assertIn('data-pos="adj."', markup)

    def test_part_of_speech_uses_common_labels(self):
        self.assertEqual(site.part_of_speech("clean"), "adj.")
        self.assertEqual(site.part_of_speech("respond"), "v.")
        self.assertEqual(site.part_of_speech("disease"), "n.")
        self.assertEqual(site.part_of_speech("quickly"), "adv.")

    def test_clean_story_text_removes_caption_noise(self):
        text = "Ben Smith/Getty Images hide caption A lot changes when. you move in with your partner."
        cleaned = site.clean_story_text(text)
        self.assertNotIn("hide caption", cleaned)
        self.assertIn("A lot changes when, you move", cleaned)

    def test_safe_word_translations_fills_missing_or_bad_values(self):
        result = site.safe_word_translations(["company", "unknown"], {"company": "เธเธฃเธดเธฉเธฑเธ—"})
        self.assertEqual(result["company"], "บริษัท")
        self.assertTrue(result["unknown"].startswith("คำว่า "))

    def test_rate_limit_pauses_provider(self):
        with tempfile.TemporaryDirectory() as temp:
            quota_path = Path(temp)
            with patch.object(site, "QUOTA_DIR", quota_path):
                quota = site.QuotaManager({"currents": 2})
                with self.assertRaises(site.ProviderError):
                    site.request_json(FakeSession([FakeResponse(429)]), quota, "currents", "https://example.test")
                row = quota.record("currents")
                self.assertFalse(quota.available("currents"))
                self.assertIn("rate_limit", row["last_error"])

    def test_auth_disables_provider(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(site, "QUOTA_DIR", Path(temp)):
                quota = site.QuotaManager({"guardian": 2})
                with self.assertRaises(site.ProviderError):
                    site.request_json(FakeSession([FakeResponse(403)]), quota, "guardian", "https://example.test")
                self.assertTrue(quota.record("guardian")["disabled"])

    def test_timeout_places_provider_on_cooldown(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(site, "QUOTA_DIR", Path(temp)):
                quota = site.QuotaManager({"nasa": 1})
                with self.assertRaises(site.ProviderError):
                    site.request_json(
                        FakeSession([site.requests.Timeout("slow")]),
                        quota,
                        "nasa",
                        "https://example.test",
                    )
                self.assertFalse(quota.available("nasa"))
                self.assertIn("timeout", quota.record("nasa")["last_error"])

    def test_candidate_collection_continues_after_provider_failure(self):
        fallback = site.demo_articles()
        config = {"demo": False}
        quota = object()
        with patch.object(site, "fetch_rss", return_value=[]), \
             patch.object(site, "fetch_currents", side_effect=site.ProviderError("currents", "rate_limit", "429")), \
             patch.object(site, "fetch_guardian", return_value=fallback), \
             patch.object(site, "fetch_nasa", return_value=[]), \
             patch.object(site, "fetch_nws", return_value=[]), \
             patch.object(site, "fetch_usgs", return_value=[]), \
             patch.object(site, "fetch_arxiv", return_value=[]):
            rows = site.collect_candidates(object(), quota, config)
        self.assertEqual(len(rows), site.DAILY_ARTICLE_COUNT)

    def test_rss_provider_parses_real_feed_items(self):
        xml = """<?xml version="1.0"?>
        <rss><channel>
          <item>
            <title>Scientists report new ocean heat record</title>
            <description>Researchers said ocean temperatures reached a new record after months of unusual heat. The report explains that warmer water can affect storms, coral reefs, and coastal communities.</description>
            <link>https://example.test/ocean-heat</link>
            <pubDate>Wed, 17 Jun 2026 10:00:00 GMT</pubDate>
            <media:thumbnail xmlns:media="http://search.yahoo.com/mrss/" url="https://example.test/ocean.jpg" />
          </item>
        </channel></rss>"""
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(site, "QUOTA_DIR", Path(temp)), \
                 patch.object(site, "RSS_FEEDS", [("Example News", "Science", "https://example.test/rss")]):
                rows = site.fetch_rss(FakeSession([FakeResponse(200, text=xml)]), site.QuotaManager({"rss_example-news-science": 3}), {"timeout": 5})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["provider"], "Example News")
        self.assertEqual(rows[0]["category"], "Science")
        self.assertEqual(rows[0]["image_url"], "https://example.test/ocean.jpg")

    def test_demo_edition_detection_requires_all_demo(self):
        rows = site.demo_articles()
        self.assertTrue(site.is_demo_edition(rows))
        mixed = [dict(rows[0], provider="BBC News"), *rows[1:]]
        self.assertFalse(site.is_demo_edition(mixed))

    def test_quota_file_is_scoped_to_current_day(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(site, "QUOTA_DIR", Path(temp)):
                quota = site.QuotaManager({"nasa": 2})
                quota.requested("nasa")
                saved = json.loads(quota.path.read_text(encoding="utf-8"))
                self.assertEqual(saved["date"], datetime.now(timezone.utc).date().isoformat())
                self.assertEqual(saved["providers"]["nasa"]["requests"], 1)

    def test_validation_rejects_incomplete_edition(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(site, "STAGING_DIR", Path(temp)):
                with self.assertRaises(RuntimeError):
                    site.validate_staging([])


if __name__ == "__main__":
    unittest.main()
