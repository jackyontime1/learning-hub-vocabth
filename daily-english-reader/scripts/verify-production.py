#!/usr/bin/env python3
"""Fail-closed verification for a deployed Learning Hub Reader build."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from update_site import speech_text_issues, translation_quality_issues  # noqa: E402

LEVELS = ("A1", "A2", "B1", "B2", "C1")
PLACEHOLDERS = (
    "คำแปลภาษาไทยสำหรับบทความตัวอย่าง",
    "เนื้อหาข่าวพูดถึงเหตุการณ์สำคัญ",
    "ควรอ่านจากย่อหน้าภาษาอังกฤษ",
    "ใจความของประโยคนี้เกี่ยวกับ",
)
SECRET_PATTERN = re.compile(
    r"cfat_[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|BEGIN PRIVATE KEY|google-tts-api-key",
    re.I,
)


def fetch(session: requests.Session, url: str, *, expect_json: bool = False):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    if expect_json:
        content_type = response.headers.get("content-type", "").lower()
        if "json" not in content_type:
            raise RuntimeError(f"Expected JSON from {url}, got {content_type}")
        return response.json()
    return response


def verify(base_url: str, expected_date: str, expected_schema: int) -> dict:
    base_url = base_url.rstrip("/") + "/"
    session = requests.Session()
    session.headers["User-Agent"] = "DailyEnglishReaderProductionVerifier/1.0"
    homepage = fetch(session, base_url)
    index = fetch(session, urljoin(base_url, "content-index.json"), expect_json=True)
    providers = fetch(session, urljoin(base_url, "provider-status.json"), expect_json=True)
    report = fetch(session, urljoin(base_url, "build-report.json"), expect_json=True)

    if len(index) != 70:
        raise RuntimeError(f"Expected 70 retained stories, got {len(index)}")
    dates = sorted({row["date"] for row in index}, reverse=True)
    if len(dates) != 7 or dates[0] != expected_date:
        raise RuntimeError(f"Expected latest seven days ending {expected_date}, got {dates}")
    for date in dates:
        rows = [row for row in index if row["date"] == date]
        if len(rows) != 10 or Counter(row["level"] for row in rows) != Counter({level: 2 for level in LEVELS}):
            raise RuntimeError(f"Invalid story distribution for {date}")

    sample_by_level = {}
    checked_images = set()
    scanned_text = homepage.text
    for row in index:
        page_url = urljoin(base_url, row["url"])
        page = fetch(session, page_url)
        scanned_text += page.text
        article_url = urljoin(page_url, "article.json")
        article = fetch(session, article_url, expect_json=True)
        if article.get("schema_version") != expected_schema:
            raise RuntimeError(f"Expected schema {expected_schema} at {article_url}")
        if article.get("provider") == "demo":
            raise RuntimeError(f"Demo article reached production: {article_url}")
        translation_issues = translation_quality_issues(article.get("text", ""), article.get("thai_text", ""))
        if translation_issues:
            raise RuntimeError(f"Unsafe Thai translation at {article_url}: {', '.join(translation_issues)}")
        speech_issues = speech_text_issues(article.get("speech_text", ""))
        if speech_issues:
            raise RuntimeError(f"Unsafe Web Speech text at {article_url}: {', '.join(speech_issues)}")
        audio = BeautifulSoup(page.text, "html.parser").select_one("#storyAudio[data-reader-text]")
        if not audio or audio.get("data-reader-text", "") != article.get("speech_text", ""):
            raise RuntimeError(f"Web Speech text is not rendered at {page_url}")
        image_url = urljoin(base_url, row["image"])
        if image_url not in checked_images:
            image_response = fetch(session, image_url)
            if "image" not in image_response.headers.get("content-type", "").lower():
                raise RuntimeError(f"Broken image content type: {image_url}")
            checked_images.add(image_url)
        if row["date"] == expected_date and row["level"] not in sample_by_level:
            thai = article.get("thai_text", "")
            if not re.search(r"[\u0e00-\u0e7f]", thai) or any(value in thai for value in PLACEHOLDERS):
                raise RuntimeError(f"Invalid Thai translation: {article_url}")
            required_image_fields = {
                "image_url", "image_local_path", "image_source", "image_author", "image_license",
                "image_attribution_url", "image_alt", "image_query", "image_relevance_score",
                "image_selected_reason", "image_is_fallback",
            }
            if not required_image_fields.issubset(article.get("image", {})):
                raise RuntimeError(f"Incomplete image metadata: {article_url}")
            sample_by_level[row["level"]] = article_url
    if set(sample_by_level) != set(LEVELS):
        raise RuntimeError("Could not verify one current article for every level")
    if providers.get("expected_toronto_date") != expected_date or not providers.get("demo_fallback_blocked"):
        raise RuntimeError("Provider diagnostics do not match the production date or free-only policy")
    if report.get("status") != "ready" or report.get("latest_date") != expected_date:
        raise RuntimeError("Build report does not confirm a ready current build")
    if report.get("schema_version") != expected_schema:
        raise RuntimeError("Build report schema mismatch")
    scanned_text += json.dumps([providers, report], ensure_ascii=False)
    if SECRET_PATTERN.search(scanned_text):
        raise RuntimeError("Possible secret exposed in production output")
    return {
        "status": "verified", "base_url": base_url, "latest_date": expected_date,
        "story_count": len(index), "dates": dates, "schema_version": expected_schema,
        "sample_articles": sample_by_level, "unique_images": len(checked_images),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-date", required=True)
    parser.add_argument("--schema", type=int, default=9)
    args = parser.parse_args()
    print(json.dumps(verify(args.base_url, args.expected_date, args.schema), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
