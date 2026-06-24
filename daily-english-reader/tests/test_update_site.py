import json
import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import update_site as site


class FakeResponse:
    def __init__(self, status, payload=None, text="", headers=None, content=None):
        self.status_code = status
        self._payload = payload or {}
        self.text = text
        self.content = content if content is not None else text.encode("utf-8")
        self.headers = headers or {}

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
            "unsplash_key": "",
            "timeout": 5,
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(site, "STATIC_DIR", root / "static"), \
                 patch.object(site, "IMAGE_CACHE_PATH", root / "images.json"), \
                 patch.object(site, "source_page_image", return_value={}), \
                 patch.object(site, "request_json", side_effect=site.ProviderError("images", "failed", "offline")):
                result = site.image_for(article, FakeSession([FakeResponse(200, payload)]), Mock(), config)
                self.assertTrue((root / "static" / "images" / result["local_filename"]).exists())
                self.assertEqual(result["image_source"], "Local Stable Diffusion")

    def test_source_page_image_extracts_og_image_and_alt(self):
        article = site.demo_articles()[0]
        html = '<meta property="og:image" content="https://example.test/topic.jpg"><meta property="og:image:alt" content="Topic image">'
        result = site.source_page_image(article, FakeSession([FakeResponse(200, text=html)]), {"timeout": 5})
        self.assertEqual(result["url"], "https://example.test/topic.jpg")
        self.assertEqual(result["alt"], "Topic image")

    def test_source_material_prefers_feed_summary_and_skips_caption_metadata(self):
        article = dict(site.demo_articles()[0], description="Clean feed summary explains the verified event and its main effect.")
        body = " ".join(f"bodyword{index}" for index in range(90))
        page = (
            "<article><figure><p>Photographer AFP via Getty Images describes a keynote address at the forum.</p></figure>"
            "<div class='photo-credit'><p>Richards AFP via contributor image credit text here.</p></div>"
            f"<p>{body}</p></article>"
        )
        result = site.source_material(article, FakeSession([FakeResponse(200, text=page)]), {"demo": False, "timeout": 5})
        self.assertTrue(result.startswith(article["description"].rstrip(".")))
        self.assertNotIn("Photographer AFP", result)
        self.assertNotIn("Richards AFP", result)
        self.assertIn("bodyword89", result)

    def test_source_media_requires_an_explicitly_allowed_provider(self):
        article = site.demo_articles()[0]
        self.assertEqual(site.source_media_license(dict(article, provider="BBC News")), "")
        self.assertIn("public-domain", site.source_media_license(dict(article, provider="USGS")))

    def test_image_query_uses_title_entities_and_category(self):
        article = site.demo_articles()[0]
        query = site.image_query(article)
        self.assertIn(article["category"].lower(), query.lower())
        self.assertIn("library", query.lower())

    def test_unique_fallback_image_is_per_article_and_has_full_metadata(self):
        first, second = site.demo_articles()[:2]
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(site, "STATIC_DIR", Path(temp) / "static"):
                a = site.unique_fallback_image(first, site.image_query(first), "test")
                b = site.unique_fallback_image(second, site.image_query(second), "test")
        self.assertNotEqual(a["local_filename"], b["local_filename"])
        self.assertTrue(a["image_is_fallback"])
        self.assertEqual(a["image_license"], "Project-owned local asset")
        self.assertGreater(a["image_relevance_score"], 0)

    def test_image_cache_version_rejects_old_shared_fallback(self):
        self.assertEqual(site.IMAGE_CACHE_VERSION, 2)

    def test_duplicate_source_image_is_rejected_with_unique_fallback(self):
        first, second = [dict(row) for row in site.demo_articles()[:2]]
        first["provider"] = second["provider"] = "USGS"
        first["image_url"] = second["image_url"] = "https://example.test/shared.jpg"
        config = {"demo": False, "timeout": 5, "unsplash_key": "", "local_image_url": "", "_used_image_urls": set()}
        image_response = FakeResponse(200, headers={"content-type": "image/jpeg"}, content=b"x" * 2000)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(site, "STATIC_DIR", root / "static"), \
                 patch.object(site, "IMAGE_CACHE_PATH", root / "images.json"), \
                 patch.object(site, "source_page_image", return_value={}), \
                 patch.object(site, "request_json", side_effect=site.ProviderError("images", "failed", "offline")):
                session = FakeSession([image_response])
                quota = Mock()
                selected = site.image_for(first, session, quota, config)
                duplicate = site.image_for(second, session, quota, config)
        self.assertFalse(selected["image_is_fallback"])
        self.assertTrue(duplicate["image_is_fallback"])
        self.assertNotEqual(selected["local_filename"], duplicate["local_filename"])

    def test_free_only_cannot_be_disabled(self):
        with patch.dict(site.os.environ, {"FREE_ONLY": "0"}, clear=False):
            with self.assertRaises(RuntimeError):
                site.config_from_env()

    def test_translation_schema_rebuilds_existing_editions(self):
        self.assertEqual(site.SCHEMA_VERSION, 9)
        self.assertEqual(site.TRANSLATION_CACHE_VERSION, 2)

    def test_translation_cache_is_scoped_to_provider_and_model(self):
        text = "A short article."
        libre = site.translation_cache_key(text, {"demo": False, "translation_provider": "libre"})
        nllb = site.translation_cache_key(text, {
            "demo": False,
            "translation_provider": "nllb",
            "nllb_model": "facebook/nllb-200-distilled-600M",
        })
        self.assertNotEqual(libre, nllb)

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

    def test_clean_story_text_repairs_common_source_typos(self):
        cleaned = site.clean_story_text("Last year 2e published a story where you've never too old to play.")
        self.assertIn("Last year we published", cleaned)
        self.assertIn("where you're never too old", cleaned)

    def test_clean_story_text_repairs_split_news_sentences(self):
        raw = (
            'For decades, sanitary napkins and. Other menstrual items have been taxed as "luxury goods" and. '
            'The price has put these products out of. Reach for many in Pakistan.'
        )
        cleaned = site.clean_story_text(raw)
        self.assertIn('sanitary napkins and other menstrual items', cleaned)
        self.assertIn('"luxury goods". The price', cleaned)
        self.assertIn('out of reach for many', cleaned)
        self.assertIn("drained and refilled", site.clean_story_text("The pool was drained and. Refilled yesterday."))
        self.assertIn("flew over the site", site.clean_story_text("The president flew over. The site on Sunday."))

    def test_clean_story_text_normalizes_nws_machine_alerts(self):
        raw = (
            "* WHAT...Flooding caused by excessive rainfall is expected. "
            "* WHERE...A portion of Oklahoma. * WHEN...Until 1015 AM CDT. "
            "* IMPACTS...Minor flooding in low-lying areas. "
            "* ADDITIONAL DETAILS... - Some locations include... Gate and Knowles. "
            "- http://www.weather.gov/safety/flood"
        )
        cleaned = site.clean_story_text(raw)
        self.assertIn("What: Flooding", cleaned)
        self.assertIn("Where: A portion", cleaned)
        self.assertIn("locations include Gate and Knowles", cleaned)
        self.assertNotIn("...", cleaned)
        self.assertNotIn("http", cleaned)

    def test_reader_text_normalizes_weather_time_units_and_hail(self):
        raw = "At 121 PM EDT, storms moved east at 25 mph. HAZARD...Wind gusts and pea size hail. SOURCE...Hail was reported at 930 PM."
        cleaned = site.prepare_reader_text(raw)
        self.assertIn("1:21 PM Eastern Daylight Time", cleaned)
        self.assertIn("9:30 PM", cleaned)
        self.assertIn("25 miles per hour", cleaned)
        self.assertIn("Hazard: Wind gusts and pea-sized hail", cleaned)
        self.assertNotIn("...", cleaned)

    def test_speech_text_repairs_known_level_fragments(self):
        body = "Depending on. data from the report, prices fell. Of, but. It, listeners understood the result."
        speech = site.make_speech_text("Housing report", body)
        self.assertNotIn("Depending on.", speech)
        self.assertNotIn("Of, but", speech)
        self.assertNotIn("It, listeners", speech)
        self.assertEqual(site.speech_text_issues(speech), [])

    def test_reader_text_preserves_paragraph_boundaries(self):
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence. Sixth sentence."
        reader = site.prepare_reader_text(text)
        self.assertEqual(len(reader.split("\n\n")), 2)

    def test_level_adapter_does_not_manufacture_mid_phrase_fragments(self):
        source = (
            "Greenspan steered the Federal Reserve for nearly two decades through some of the longest "
            "economic booms in United States history, but his listeners were sometimes confused by Fedspeak."
        )
        result = " ".join(site.simplify_sentence(source, 12, True))
        self.assertNotIn("some. Of", result)
        self.assertNotIn("but.", result.lower())
        self.assertIn("But his listeners", result)

    def test_sentence_simplifier_does_not_split_at_descriptive_commas(self):
        source = (
            "Israel targeted the entire city, apart from a small, largely Christian enclave on the seaside, "
            "saying it was targeting fighters."
        )
        result = " ".join(site.simplify_sentence(source, 18, False))
        self.assertNotIn("small. Largely", result)

    def test_written_measurement_and_translated_unit_are_preserved(self):
        source = "The city is twelve miles north of the border."
        normalized = site.normalize_written_measurements(source)
        self.assertIn("12 miles", normalized)
        repaired = site.repair_translated_facts(source, "เมืองอยู่ห่างจากชายแดนไปทางเหนือ 12 กิโลเมตร")
        self.assertIn("12 ไมล์", repaired)
        self.assertNotIn("กิโลเมตร", repaired)
        self.assertEqual(site.translation_quality_issues(source, repaired), [])
        rate_source = "Wind moved at 25 miles per hour and later reached 60 miles per hour."
        rate_target = "ลมเคลื่อนที่ 25 มิลต่อชั่วโมง และต่อมาเพิ่มเป็น 60 เมลต่อชั่วโมง"
        repaired_rate = site.repair_translated_facts(rate_source, rate_target)
        self.assertIn("25 ไมล์ต่อชั่วโมง", repaired_rate)
        self.assertIn("60 ไมล์ต่อชั่วโมง", repaired_rate)

    def test_translation_quality_accepts_equivalent_clock_separators(self):
        source = "The warning began at 9:33 PM and the report was issued at 9:30 PM."
        translated = "คำเตือนเริ่มเวลา 9.33 น. และรายงานออกเมื่อเวลา 9.30 น."
        self.assertFalse(any(issue.startswith("missing-number:") for issue in site.translation_quality_issues(source, translated)))
        self.assertNotIn("missing-time-period", site.translation_quality_issues(source, translated))

    def test_non_substantive_fragments_do_not_block_translation(self):
        self.assertTrue(site.is_non_substantive_fragment("Alan Greenspan."))
        self.assertTrue(site.is_non_substantive_fragment("Richards/AFP via Getty Images photo credit."))
        self.assertFalse(site.is_non_substantive_fragment("Greenspan died on Monday at age 100."))

    def test_safe_word_translations_fills_missing_or_bad_values(self):
        result = site.safe_word_translations(["company", "unknown"], {"company": "เธเธฃเธดเธฉเธฑเธ—"})
        self.assertEqual(result["company"], "บริษัท")
        self.assertNotIn("คำว่า", result["unknown"])

    def test_news_glossary_uses_real_thai_meanings(self):
        result = site.safe_word_translations(["filmed", "diver", "shark", "rare"], {})
        self.assertEqual(result["filmed"], "ถ่ายวิดีโอ")
        self.assertEqual(result["diver"], "นักดำน้ำ")
        self.assertEqual(result["shark"], "ฉลาม")
        self.assertEqual(result["rare"], "หายาก")

    def test_natural_thai_article_uses_story_content(self):
        raw = {
            "provider": "BBC News",
            "category": "Science",
            "level": "A1",
            "title": "Rare footage captured of Great White shark in Mediterranean Sea",
            "description": "A volunteer diver has described shaking as he filmed his encounter with an endangered Great White shark between Tunisia and Sicily.",
        }
        text = "A diver filmed an incredibly rare encounter with a Great White shark in the Mediterranean Sea."
        thai = site.natural_thai_article(raw, text)
        self.assertIn("ฉลามขาวใหญ่", thai)
        self.assertIn("นักดำน้ำ", thai)
        self.assertIn("ถ่ายวิดีโอ", thai)

    def test_natural_thai_article_translates_whole_article_not_word_glosses(self):
        raw = {
            "provider": "NPR",
            "category": "Health",
            "level": "A1",
            "title": "Pakistan ends 'luxury tax' on menstrual products, contraceptives. Will prices drop?",
            "description": (
                "In Pakistan, taxes on menstrual products can add up. Activists have long worked to change this. "
                "Now a new budget wipes out the 18% sales tax. But questions remain about the impact on prices."
            ),
        }
        text = (
            "Menstrual products have been subject to an 18% Sales tax in Pakistan, prompting protests. "
            "The budget for next fiscal year has the sales tax on these products dropping from 18% to zero. "
            "For decades, sanitary napkins and other menstrual items have been taxed as luxury goods. "
            "The price has put these products out of reach for many in Pakistan."
        )
        thai = site.natural_thai_article(raw, text)
        self.assertIn("ข่าวนี้มาจาก NPR", thai)
        self.assertIn("เนื้อหาข่าวคือ", thai)
        self.assertIn("ปากีสถาน", thai)
        self.assertIn("ภาษีขาย 18%", thai)
        self.assertIn("ผ้าอนามัย", thai)
        self.assertNotIn("drop =", thai)
        self.assertNotIn("tax =", thai)
        self.assertNotIn("ใจความของประโยคนี้เกี่ยวกับ", thai)

    def test_full_thai_article_uses_complete_service_translation(self):
        raw = {
            "provider": "BBC News",
            "category": "World",
            "level": "A2",
        }
        text = "A white cat eats a dog near the house while its owner watches from the garden."
        translated = "แมวสีขาวกินสุนัขใกล้บ้าน ขณะที่เจ้าของมองดูเหตุการณ์จากในสวน"
        thai = site.full_thai_article(raw, text, translated)
        self.assertIn("ข่าวนี้มาจาก BBC News", thai)
        self.assertIn("เนื้อหาข่าวคือ", thai)
        self.assertIn(translated, thai)
        self.assertNotIn("ควรอ่านจากย่อหน้าภาษาอังกฤษ", thai)

    def test_full_thai_translation_rejects_placeholder_text(self):
        source = "Researchers published a detailed report about changes in the national economy."
        placeholder = "เนื้อหาข่าวพูดถึงเหตุการณ์สำคัญและผลกระทบที่ผู้อ่านควรติดตามต่อ"
        self.assertFalse(site.is_useful_thai_translation(source, placeholder))
        self.assertFalse(site.is_useful_thai_translation(source, ""))

    def test_translation_quality_rejects_repeated_thai_words(self):
        source = "Inflation rose because energy prices increased across the country."
        translated = "อัตรา " * 20
        self.assertIn("repeated-word-run", site.translation_quality_issues(source, translated))

    def test_translation_quality_rejects_repeated_thai_ngrams(self):
        source = "Energy prices rose quickly and affected families across the country."
        translated = "ราคาพลังงาน สูงขึ้น " * 10
        issues = site.translation_quality_issues(source, translated)
        self.assertTrue(any(issue.startswith("repeated-2-gram") for issue in issues))

    def test_translation_quality_rejects_lao_script(self):
        source = "The government reduced restrictions after the meeting."
        translated = "รัฐบาลลดຜ່ອນข้อจำกัดหลังการประชุมอย่างเป็นทางการ"
        self.assertIn("unexpected-non-thai-script", site.translation_quality_issues(source, translated))

    def test_translation_quality_preserves_months(self):
        source = "The government announced the change in March after a public meeting."
        wrong = "รัฐบาลประกาศการเปลี่ยนแปลงในเดือนมกราคมหลังการประชุมกับประชาชน"
        good = "รัฐบาลประกาศการเปลี่ยนแปลงในเดือนมีนาคมหลังการประชุมกับประชาชน"
        self.assertIn("missing-month:March", site.translation_quality_issues(source, wrong))
        self.assertNotIn("missing-month:March", site.translation_quality_issues(source, good))

    def test_translation_quality_preserves_time_and_percent(self):
        source = "At 1:21 PM, prices increased by 3.2 percent after the report."
        wrong = "เวลา 2:21 น. ราคาสินค้าเพิ่มขึ้นหลังรายงาน"
        good = "เวลา 1:21 น. ราคาสินค้าเพิ่มขึ้น 3.2 เปอร์เซ็นต์หลังรายงาน"
        wrong_issues = site.translation_quality_issues(source, wrong)
        self.assertTrue(any(issue.startswith("missing-number:") for issue in wrong_issues))
        self.assertIn("missing-percent-unit", wrong_issues)
        self.assertFalse(any(issue.startswith("missing-number:") for issue in site.translation_quality_issues(source, good)))

    def test_translation_quality_preserves_all_numbers(self):
        source = "Officials reported 1,003 cases, 254 deaths, and 100 recoveries."
        translated = "เจ้าหน้าที่รายงานผู้ป่วย 1,003 ราย ผู้เสียชีวิต 254 ราย และผู้หายป่วย 100 ราย"
        self.assertFalse(any(issue.startswith("missing-number:") for issue in site.translation_quality_issues(source, translated)))
        missing = translated.replace("254", "")
        self.assertTrue(any("254" in issue for issue in site.translation_quality_issues(source, missing)))

    def test_translation_quality_rejects_collapsed_paragraphs(self):
        source = "One complete sentence. Another complete sentence. A third complete sentence.\n\nA fourth sentence. A fifth sentence. A sixth sentence."
        translated = "นี่คือประโยคแรก. นี่คือประโยคที่สอง. นี่คือประโยคที่สาม. นี่คือประโยคที่สี่."
        self.assertIn("collapsed-paragraphs", site.translation_quality_issues(source, translated))

    def test_mojibake_detection_keeps_normal_thai_words(self):
        self.assertFalse(site.looks_mojibake("เธอบอกว่าเนื้อหาข่าวนี้อ่านง่าย"))
        self.assertTrue(site.looks_mojibake("เธ\x82เน\x88เธฒเธง"))

    def test_translator_retries_an_empty_cached_article_translation(self):
        text = "A white cat eats a dog near the house."
        words = ["cat"]
        response = FakeResponse(200, {
            "translatedText": ["แมวสีขาวกินสุนัขใกล้บ้านหลังหนึ่ง", "แมว"],
        })
        config = {
            "demo": False,
            "translation_provider": "libre",
            "libre_url": "http://127.0.0.1:5000",
            "libre_key": "",
            "timeout": 5,
        }
        key = site.translation_cache_key(text, config)
        with tempfile.TemporaryDirectory() as temp:
            cache_path = Path(temp) / "translations.json"
            cache_path.write_text(json.dumps({key: {"thai_text": "", "words": {"cat": "แมว"}}}), encoding="utf-8")
            with patch.object(site, "TRANSLATION_CACHE_PATH", cache_path):
                translator = site.Translator(FakeSession([response]), config)
                thai, translations = translator.translate(text, words)
        self.assertEqual(thai, "แมวสีขาวกินสุนัขใกล้บ้านหลังหนึ่ง")
        self.assertEqual(translations["cat"], "แมว")

    def test_translator_rejects_bad_cached_translation_and_records_reason(self):
        text = "Housing prices fell after the economic report was published."
        words = ["housing"]
        config = {"demo": False, "translation_provider": "nllb", "nllb_model": "local-test"}
        key = site.translation_cache_key(text, config)
        bad = "อัตรา " * 20
        good = "ราคาที่อยู่อาศัยลดลงหลังจากมีการเผยแพร่รายงานทางเศรษฐกิจ"
        with tempfile.TemporaryDirectory() as temp:
            cache_path = Path(temp) / "translations.json"
            cache_path.write_text(json.dumps({key: {"thai_text": bad, "words": {"housing": "ที่อยู่อาศัย"}}}), encoding="utf-8")
            with patch.object(site, "TRANSLATION_CACHE_PATH", cache_path):
                translator = site.Translator(FakeSession([]), config)
                with patch.object(translator, "_nllb_translate", return_value=good) as translate:
                    thai, _ = translator.translate(text, words)
        self.assertEqual(thai, good)
        self.assertEqual(translator.diagnostics_summary()["cache_rejections"], 1)
        translate.assert_called_once_with(text)

    def test_nllb_retries_with_strict_repetition_control(self):
        text = "Housing prices fell after the economic report was published."
        config = {"demo": False, "translation_provider": "nllb", "nllb_model": "local-test"}
        bad = "อัตรา " * 20
        good = "ราคาที่อยู่อาศัยลดลงหลังจากมีการเผยแพร่รายงานทางเศรษฐกิจ"
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(site, "TRANSLATION_CACHE_PATH", Path(temp) / "translations.json"):
                translator = site.Translator(FakeSession([]), config)
                with patch.object(translator, "_nllb_translate", side_effect=[bad, good]) as translate:
                    thai, _ = translator.translate(text, ["housing"])
        self.assertEqual(thai, good)
        self.assertEqual(translate.call_count, 2)
        translate.assert_any_call(text, strict=True)

    def test_nllb_provider_translates_article_once_and_keeps_local_glossary(self):
        text = "A white cat eats a dog near the house."
        words = ["cat", "house"]
        config = {
            "demo": False,
            "translation_provider": "nllb",
            "nllb_model": "facebook/nllb-200-distilled-600M",
        }
        with tempfile.TemporaryDirectory() as temp:
            cache_path = Path(temp) / "translations.json"
            with patch.object(site, "TRANSLATION_CACHE_PATH", cache_path):
                translator = site.Translator(FakeSession([]), config)
                with patch.object(translator, "_nllb_translate", return_value="แมวสีขาวกินสุนัขใกล้บ้าน") as translate:
                    thai, translations = translator.translate(text, words)
        translate.assert_called_once_with(text)
        self.assertEqual(thai, "แมวสีขาวกินสุนัขใกล้บ้าน")
        self.assertEqual(translations["house"], "บ้าน")

    def test_translation_chunks_preserve_all_sentences(self):
        text = "One short sentence. Another short sentence. A final short sentence."
        chunks = site.translation_chunks(text, max_words=5)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(" ".join(chunks), text)

    def test_translation_preprocessing_keeps_meaning_but_simplifies_idioms(self):
        source = "Sanitary napkins have been subject to tax and are out of reach for many people."
        simplified = site.simplify_translation_source(source)
        self.assertIn("menstrual pads", simplified.lower())
        self.assertIn("had tax", simplified.lower())
        self.assertIn("too expensive for", simplified.lower())

    def test_exact_curated_translation_is_used_only_for_the_whole_sentence(self):
        sentence = "For decades, sanitary napkins and other menstrual items have been taxed as luxury goods."
        self.assertEqual(
            site.exact_translated_phrase(sentence),
            "เป็นเวลาหลายสิบปี ผ้าอนามัยและสินค้าสำหรับประจำเดือนอื่น ๆ ถูกเก็บภาษีเหมือนสินค้าฟุ่มเฟือย",
        )
        self.assertEqual(site.exact_translated_phrase(sentence + " Prices stayed high."), "")

    def test_naturalize_thai_repairs_common_model_spelling_and_terms(self):
        raw = "กระดาษประจําเดือนแพงเกินไปสําหรับคนหลายคน และทําให้เกิดปัญหา"
        result = site.naturalize_thai(raw)
        self.assertIn("ผ้าอนามัย", result)
        self.assertIn("สำหรับหลายคน", result)
        self.assertIn("ทำให้", result)

    def test_naturalize_thai_repairs_human_rights_mistranslation(self):
        result = site.naturalize_thai("รัฐบาลถูกกล่าวหาว่าข่มขืนสิทธิมนุษยชนของประชาชน ลมแรง 20 knots")
        self.assertIn("ละเมิดสิทธิมนุษยชน", result)
        self.assertNotIn("ข่มขืนสิทธิมนุษยชน", result)
        self.assertIn("20 นอต", result)

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

    def test_nws_request_uses_supported_status_parameter_only(self):
        session = Mock()
        session.get.return_value = FakeResponse(200, {"features": []})
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(site, "QUOTA_DIR", Path(temp)):
                rows = site.fetch_nws(session, site.QuotaManager({"nws": 2}), {"timeout": 5})
        self.assertEqual(rows, [])
        self.assertEqual(session.get.call_args.kwargs["params"], {"status": "actual"})

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
                self.assertEqual(saved["date"], site.expected_edition_date())
                self.assertEqual(saved["providers"]["nasa"]["requests"], 1)

    def test_provider_status_explains_attempts_selection_and_skips(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(site, "QUOTA_DIR", Path(temp)):
                quota = site.QuotaManager({"rss_example": 3})
                quota.requested("rss_example")
                quota.succeeded("rss_example")
                quota.selected("rss_example", 2)
                quota.skipped("rss_example", "duplicate article")
                row = quota.public_status()["providers"]["rss_example"]
        self.assertTrue(row["attempted"])
        self.assertEqual(row["request_count"], 1)
        self.assertEqual(row["success_count"], 1)
        self.assertEqual(row["selected_count"], 2)
        self.assertEqual(row["skip_reasons"]["duplicate article"], 1)

    def test_provider_status_keeps_the_build_start_date_across_toronto_midnight(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(site, "QUOTA_DIR", Path(temp)), \
                 patch.object(site, "expected_edition_date", return_value="2026-06-23"):
                quota = site.QuotaManager({})
                status = quota.public_status(expected_date="2026-06-22")
        self.assertEqual(status["expected_toronto_date"], "2026-06-22")

    def test_validation_rejects_incomplete_edition(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(site, "STAGING_DIR", Path(temp)):
                with self.assertRaises(RuntimeError):
                    site.validate_staging([])


if __name__ == "__main__":
    unittest.main()
