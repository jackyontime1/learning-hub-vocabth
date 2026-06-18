#!/usr/bin/env python3
"""Build the free-only Daily English Reader static site."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
import wave
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pyttsx3
import requests
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from summa.summarizer import summarize as textrank_summarize

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"
QUOTA_DIR = DATA_DIR / "quota"
AUDIO_CACHE_DIR = DATA_DIR / "audio"
TRANSLATION_CACHE_PATH = CACHE_DIR / "translations.json"
IMAGE_CACHE_PATH = CACHE_DIR / "images.json"
TEMPLATE_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
SITE_DIR = ROOT / "site"
STAGING_DIR = ROOT / ".site-staging"
BACKUP_DIR = ROOT / ".site-backup"

CURRENTS_URL = "https://api.currentsapi.services/v1/latest-news"
GUARDIAN_URL = "https://content.guardianapis.com/search"
NASA_APOD_URL = "https://api.nasa.gov/planetary/apod"
NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"
USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson"
ARXIV_URL = "https://export.arxiv.org/api/query"
UNSPLASH_URL = "https://api.unsplash.com/search/photos"
OPENVERSE_URL = "https://api.openverse.org/v1/images/"
COMMONS_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "DailyEnglishReader/2.0 (personal educational project; contact=local)"
SCHEMA_VERSION = 5
LEVELS = ("A1", "A2", "B1", "B2", "C1")
TARGET_PER_LEVEL = 2
DAILY_ARTICLE_COUNT = len(LEVELS) * TARGET_PER_LEVEL

RSS_FEEDS = [
    ("CBC News", "Canada", "https://www.cbc.ca/webfeed/rss/rss-canada"),
    ("CBC News", "World", "https://www.cbc.ca/webfeed/rss/rss-world"),
    ("CBC News", "Business", "https://www.cbc.ca/webfeed/rss/rss-business"),
    ("BBC News", "World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("BBC News", "Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("BBC News", "Science", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
    ("NPR", "World", "https://feeds.npr.org/1004/rss.xml"),
    ("NPR", "Business", "https://feeds.npr.org/1006/rss.xml"),
    ("NPR", "Health", "https://feeds.npr.org/1128/rss.xml"),
]

DEMO_IMAGE_MAP = {
    "City library adds solar panels to cut energy costs": "demo-solar-library.png",
    "Short walking breaks may help office workers focus": "demo-walking-break.png",
    "Scientists map a large coral nursery in the Pacific": "demo-coral-nursery.png",
    "Small robots help farmers check crops": "demo-farm-robots.png",
    "New sensors improve early earthquake reports": "demo-earthquake-sensors.png",
    "Researchers extend the life of reusable batteries": "demo-battery-lab.png",
}

STOPWORDS = {
    "a", "about", "after", "again", "against", "all", "also", "an", "and", "any",
    "are", "as", "at", "be", "because", "been", "before", "being", "between", "both",
    "but", "by", "can", "could", "did", "do", "does", "doing", "down", "during", "each",
    "for", "from", "had", "has", "have", "he", "her", "here", "him", "his", "how", "if",
    "in", "into", "is", "it", "its", "more", "most", "no", "not", "of", "on", "or",
    "other", "our", "out", "over", "same", "she", "so", "some", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "this", "those", "through", "to",
    "under", "up", "very", "was", "we", "were", "what", "when", "where", "which", "while",
    "who", "will", "with", "would", "you", "your",
}

SIMPLE_REPLACEMENTS = {
    "approximately": "about", "commence": "start", "conclude": "end",
    "consequently": "so", "demonstrate": "show", "determine": "find out",
    "difficulties": "problems", "numerous": "many", "obtain": "get",
    "purchase": "buy", "require": "need", "residents": "local people",
    "significant": "important", "subsequently": "later", "utilize": "use",
}

DETERMINERS = {"a", "an", "the", "this", "that", "these", "those", "each", "every", "some", "any"}
PRONOUNS = {"i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them", "who", "which", "that"}
PREPOSITIONS = {
    "about", "above", "after", "against", "around", "at", "before", "between", "by", "during",
    "for", "from", "in", "into", "near", "of", "on", "over", "through", "to", "under", "with",
}
CONJUNCTIONS = {"and", "but", "or", "because", "if", "while", "although", "so"}
COMMON_VERBS = {
    "add", "affect", "allow", "ask", "be", "become", "begin", "bring", "build", "buy", "call",
    "can", "change", "check", "come", "could", "cut", "do", "expect", "find", "get", "give",
    "go", "have", "help", "include", "keep", "know", "lead", "learn", "make", "may", "move",
    "need", "play", "provide", "reduce", "report", "respond", "run", "say", "see", "send",
    "show", "start", "take", "test", "try", "use", "walk", "will", "work", "would",
}
COMMON_ADJECTIVES = {
    "able", "active", "annual", "big", "clean", "clear", "daily", "different", "dry", "early",
    "fast", "free", "good", "great", "large", "local", "long", "new", "old", "public", "real",
    "short", "small", "strong", "young",
}

THAI_CATEGORY_LABELS = {
    "business": "ธุรกิจและเศรษฐกิจ",
    "canada": "ข่าวแคนาดา",
    "environment": "สิ่งแวดล้อม",
    "health": "สุขภาพ",
    "science": "วิทยาศาสตร์",
    "technology": "เทคโนโลยี",
    "world": "ข่าวต่างประเทศ",
}

THAI_WORDS = {
    "able": "ทำได้", "about": "เกี่ยวกับ", "access": "เข้าถึง", "according": "ตามข้อมูลจาก",
    "active": "คล่องตัว", "add": "เพิ่ม", "after": "หลังจาก", "again": "อีกครั้ง",
    "against": "ต่อต้าน", "agency": "หน่วยงาน", "agreement": "ข้อตกลง", "ai": "ปัญญาประดิษฐ์",
    "air": "อากาศ", "allow": "อนุญาต", "also": "อีกด้วย", "announce": "ประกาศ",
    "announced": "ประกาศ", "area": "พื้นที่", "around": "รอบ ๆ", "ask": "ถาม",
    "attack": "โจมตี", "available": "มีให้ใช้", "bank": "ธนาคาร", "battery": "แบตเตอรี่",
    "become": "กลายเป็น", "before": "ก่อน", "begin": "เริ่ม", "big": "ใหญ่",
    "billion": "พันล้าน", "bring": "นำมา", "build": "สร้าง", "business": "ธุรกิจ",
    "buy": "ซื้อ", "call": "เรียก", "called": "เรียกว่า", "canada": "แคนาดา",
    "canadian": "ชาวแคนาดา", "care": "การดูแล", "case": "คดี", "cause": "เป็นสาเหตุ",
    "change": "เปลี่ยน", "children": "เด็ก", "city": "เมือง", "claim": "กล่าวอ้าง",
    "clean": "สะอาด", "climate": "สภาพภูมิอากาศ", "come": "มา", "community": "ชุมชน",
    "company": "บริษัท", "concern": "ความกังวล", "confirmed": "ยืนยัน", "cost": "ค่าใช้จ่าย",
    "country": "ประเทศ", "court": "ศาล", "create": "สร้าง", "cut": "ลด",
    "data": "ข้อมูล", "day": "วัน", "deal": "ข้อตกลง", "decision": "การตัดสินใจ",
    "demand": "ความต้องการ", "different": "แตกต่าง", "disease": "โรค", "early": "เร็วขึ้น",
    "economic": "ทางเศรษฐกิจ", "economy": "เศรษฐกิจ", "education": "การศึกษา",
    "effort": "ความพยายาม", "energy": "พลังงาน", "event": "เหตุการณ์", "expect": "คาดว่า",
    "family": "ครอบครัว", "farm": "ฟาร์ม", "find": "พบ", "firm": "บริษัท",
    "food": "อาหาร", "future": "อนาคต", "game": "เกม", "global": "ระดับโลก",
    "government": "รัฐบาล", "group": "กลุ่ม", "grow": "เติบโต", "health": "สุขภาพ",
    "help": "ช่วย", "home": "บ้าน", "include": "รวมถึง", "increase": "เพิ่มขึ้น",
    "industry": "อุตสาหกรรม", "information": "ข้อมูล", "international": "ระหว่างประเทศ",
    "job": "งาน", "jobs": "ตำแหน่งงาน", "keep": "รักษา", "large": "ใหญ่",
    "law": "กฎหมาย", "leader": "ผู้นำ", "life": "ชีวิต", "local": "ท้องถิ่น",
    "make": "ทำให้", "market": "ตลาด", "may": "อาจ", "million": "ล้าน",
    "minister": "รัฐมนตรี", "money": "เงิน", "month": "เดือน", "move": "ย้าย",
    "national": "ระดับประเทศ", "need": "ต้องการ", "new": "ใหม่", "news": "ข่าว",
    "official": "เจ้าหน้าที่", "oil": "น้ำมัน", "old": "เก่า", "parent": "บริษัทแม่",
    "people": "ผู้คน", "plan": "แผน", "policy": "นโยบาย", "power": "พลังงาน",
    "price": "ราคา", "problem": "ปัญหา", "program": "โครงการ", "project": "โครงการ",
    "public": "สาธารณะ", "rate": "อัตรา", "report": "รายงาน", "research": "งานวิจัย",
    "researcher": "นักวิจัย", "risk": "ความเสี่ยง", "school": "โรงเรียน",
    "science": "วิทยาศาสตร์", "scientist": "นักวิทยาศาสตร์", "security": "ความปลอดภัย",
    "service": "บริการ", "share": "แบ่งปัน", "short": "สั้น", "show": "แสดงให้เห็น",
    "small": "เล็ก", "social": "สังคม", "source": "แหล่งข้อมูล", "space": "อวกาศ",
    "state": "รัฐ", "study": "การศึกษา", "system": "ระบบ", "tax": "ภาษี",
    "team": "ทีม", "technology": "เทคโนโลยี", "test": "ทดสอบ", "time": "เวลา",
    "today": "วันนี้", "tool": "เครื่องมือ", "use": "ใช้", "user": "ผู้ใช้",
    "war": "สงคราม", "water": "น้ำ", "week": "สัปดาห์", "woman": "ผู้หญิง",
    "women": "ผู้หญิง", "work": "งาน", "worker": "คนทำงาน", "workers": "พนักงาน",
    "world": "โลก", "year": "ปี", "young": "อายุน้อย",
}

DEMO_TOPICS = [
    ("demo-library", "City library adds solar panels to cut energy costs", "Environment",
     "A public library has installed new solar panels on its roof. Officials say the project will lower electricity costs and teach visitors about clean energy. The library expects the panels to provide about one third of the building's annual power.",
     "ห้องสมุดของเมืองติดตั้งแผงโซลาร์เซลล์บนหลังคา โครงการนี้ช่วยลดค่าไฟและสอนผู้มาเยือนเรื่องพลังงานสะอาด"),
    ("demo-walking", "Short walking breaks may help office workers focus", "Health",
     "A workplace study found that short walking breaks helped workers feel more alert. Participants walked for five minutes every hour. Researchers said larger studies are still needed.",
     "งานวิจัยในที่ทำงานพบว่าการเดินพักสั้น ๆ อาจช่วยให้พนักงานตื่นตัวและมีสมาธิมากขึ้น"),
    ("demo-ocean", "Scientists map a large coral nursery in the Pacific", "Science",
     "Marine scientists have mapped a large coral nursery in the Pacific Ocean. The team used underwater cameras to count young coral and study water conditions. The findings may help future conservation work.",
     "นักวิทยาศาสตร์ทางทะเลทำแผนที่แหล่งอนุบาลปะการังขนาดใหญ่ในมหาสมุทรแปซิฟิก"),
    ("demo-robots", "Small robots help farmers check crops", "Technology",
     "Engineers have tested small robots that move between farm rows and photograph crops. Software checks the images for signs of disease and dry soil. Farmers can use the reports to respond earlier.",
     "วิศวกรทดสอบหุ่นยนต์ขนาดเล็กที่ช่วยตรวจพืชและค้นหาสัญญาณของโรคหรือดินแห้ง"),
    ("demo-quake", "New sensors improve early earthquake reports", "World",
     "A network of new ground sensors is improving early earthquake reports. The devices send movement data to researchers within seconds. Faster information can help emergency teams understand where damage may be strongest.",
     "เครือข่ายเซนเซอร์ภาคพื้นดินชุดใหม่ช่วยให้รายงานแผ่นดินไหวเบื้องต้นรวดเร็วขึ้น"),
    ("demo-battery", "Researchers extend the life of reusable batteries", "Business",
     "Researchers have developed a charging method that may extend the useful life of reusable batteries. The method carefully changes the electrical current during charging. Longer battery life could reduce waste and operating costs.",
     "นักวิจัยพัฒนาวิธีชาร์จที่อาจยืดอายุแบตเตอรี่แบบใช้ซ้ำและช่วยลดขยะกับค่าใช้จ่าย"),
]


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        temporary = Path(handle.name)
    temporary.replace(path)


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback
    except (OSError, json.JSONDecodeError):
        return fallback


def normalize(value: str) -> str:
    raw = str(value or "")
    text = BeautifulSoup(raw, "html.parser").get_text(" ") if "<" in raw and ">" in raw else html.unescape(raw)
    return re.sub(r"\s+", " ", text).strip()


def slugify(value: str, limit: int = 72) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:limit].rstrip("-") or "story"


def sentence_split(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", normalize(text)) if part.strip()]


def clean_story_text(text: str) -> str:
    text = normalize(text)
    text = re.sub(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+){0,3}/(?:iStockphoto|Getty Images|AP|Reuters)[^.!?]*hide caption\b", " ", text)
    text = re.sub(r"\bhide caption\b", " ", text, flags=re.I)
    text = re.sub(r"\b(?:SCOTT DETROW|A MARTÍNEZ|HOST|BYLINE|EDITOR'S NOTE):\s*", " ", text, flags=re.I)
    text = re.sub(r"\b(?:Image source|Getty Images|Reuters|Associated Press|AP Photo)\b[^.!?]*(?:\.|$)", " ", text, flags=re.I)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\b([A-Z])\s*\.\s+([A-Z][a-z])", r"\1. \2", text)
    text = re.sub(r"(?<!\b[A-Z])\.\s+(?=[a-z])", ", ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def sentence_budget(level: str) -> tuple[int, int]:
    return {
        "A1": (8, 70),
        "A2": (10, 105),
        "B1": (12, 145),
        "B2": (14, 190),
        "C1": (16, 230),
    }.get(level, (12, 145))


def trim_to_word_budget(sentences: list[str], max_words: int) -> str:
    output: list[str] = []
    count = 0
    for sentence in sentences:
        words = sentence.split()
        if not words:
            continue
        if output and count + len(words) > max_words:
            break
        output.append(sentence)
        count += len(words)
    return " ".join(output).strip()


def english_label_for_category(category: str) -> str:
    return THAI_CATEGORY_LABELS.get(category.lower(), category)


def thai_gloss(word: str) -> str:
    key = word.lower().strip("'")
    if key in THAI_WORDS:
        return THAI_WORDS[key]
    stem = re.sub(r"(ing|ed|es|s)$", "", key)
    if stem in THAI_WORDS:
        return THAI_WORDS[stem]
    if key.endswith("ly"):
        return "อย่าง" + key[:-2]
    if key.endswith(("tion", "sion", "ment", "ness", "ity")):
        return "เรื่อง/ภาวะของ " + key
    return f"คำว่า {word}"


def safe_word_translations(words: list[str], translated: dict[str, str] | None = None) -> dict[str, str]:
    output: dict[str, str] = {}
    for word in words:
        value = normalize((translated or {}).get(word, ""))
        if not value or value.lower() == word.lower() or re.search(r"เธ|เน|โ€", value):
            value = thai_gloss(word)
        output[word] = value
    return output


def natural_thai_article(raw: dict[str, Any], text: str) -> str:
    category = english_label_for_category(raw.get("category", "news"))
    provider = raw.get("provider", "แหล่งข่าว")
    title = raw.get("title", "")
    numbers = re.findall(r"\b\d[\d,.]*(?:%| per cent| percent| million| billion| years?| days?)?\b", text, flags=re.I)[:4]
    keywords = [word for word in vocabulary_words(" ".join([title, raw.get("description", ""), text])) if word not in STOPWORDS][:8]
    keyword_text = " / ".join(f"{word} = {thai_gloss(word)}" for word in keywords[:5])
    number_text = f" ตัวเลขที่ควรสังเกตในข่าวนี้คือ {', '.join(numbers)}." if numbers else ""
    level = raw.get("level", "")
    focus = {
        "business": "ความเคลื่อนไหวด้านธุรกิจ เศรษฐกิจ หรือการจ้างงาน",
        "canada": "เหตุการณ์หรือการตัดสินใจที่เกี่ยวข้องกับแคนาดา",
        "environment": "ผลกระทบต่อธรรมชาติ สิ่งแวดล้อม หรือสภาพอากาศ",
        "health": "ประเด็นด้านสุขภาพ การแพทย์ หรือคุณภาพชีวิต",
        "science": "การค้นพบ งานวิจัย หรือข้อมูลทางวิทยาศาสตร์",
        "technology": "เทคโนโลยี เครื่องมือดิจิทัล หรือผลกระทบของ AI",
        "world": "เหตุการณ์สำคัญในต่างประเทศและผลกระทบที่ตามมา",
    }.get(raw.get("category", "").lower(), "ประเด็นสำคัญที่ควรติดตาม")
    return (
        f"ข่าวนี้มาจาก {provider} อยู่ในหมวด{category} และถูกเรียบเรียงเป็นระดับ {level}. "
        f"หัวข้อข่าวคือ “{title}”. โดยรวมแล้ว ข่าวนี้พูดถึง{focus} "
        f"ผู้อ่านควรจับใจความว่าเกิดอะไรขึ้น ใครได้รับผลกระทบ และเรื่องนี้อาจเปลี่ยนสถานการณ์ต่อไปอย่างไร."
        f"{number_text} คำสำคัญที่ควรรู้: {keyword_text}."
    )


def parse_date(value: str | None) -> datetime:
    if not value:
        return utc_now()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
            return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
        except (TypeError, ValueError, IndexError):
            return utc_now()


def stable_id(provider: str, url: str, title: str) -> str:
    return hashlib.sha256(f"{provider}|{url}|{title}".encode()).hexdigest()[:18]


def xml_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def child_text(node: ET.Element, *names: str) -> str:
    wanted = {name.lower() for name in names}
    for child in node:
        if xml_name(child.tag) in wanted:
            return normalize(" ".join(child.itertext()))
    return ""


def child_attr(node: ET.Element, child_name: str, attr_name: str) -> str:
    for child in node:
        if xml_name(child.tag) == child_name.lower():
            for key, value in child.attrib.items():
                if key.rsplit("}", 1)[-1].lower() == attr_name.lower():
                    return value
    return ""


def add_query(url: str, values: dict[str, str]) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update(values)
    return urlunparse(parsed._replace(query=urlencode(query)))


class ProviderError(RuntimeError):
    def __init__(self, provider: str, kind: str, message: str) -> None:
        super().__init__(message)
        self.provider = provider
        self.kind = kind


class QuotaManager:
    def __init__(self, limits: dict[str, int]) -> None:
        self.day = utc_now().date().isoformat()
        self.path = QUOTA_DIR / f"{self.day}.json"
        self.limits = limits
        self.state = load_json(self.path, {"date": self.day, "providers": {}})

    def record(self, provider: str) -> dict[str, Any]:
        return self.state["providers"].setdefault(provider, {
            "requests": 0, "errors": 0, "disabled": False, "cooldown_until": "", "last_error": "",
        })

    def available(self, provider: str) -> bool:
        record = self.record(provider)
        limit = self.limits.get(provider, 30 if provider.startswith("rss_") else 1)
        if record["disabled"] or record["requests"] >= limit:
            return False
        cooldown = parse_date(record["cooldown_until"]) if record["cooldown_until"] else None
        return not cooldown or cooldown <= utc_now()

    def requested(self, provider: str) -> None:
        self.record(provider)["requests"] += 1
        self.save()

    def failed(self, provider: str, kind: str, message: str) -> None:
        record = self.record(provider)
        record["errors"] += 1
        record["last_error"] = f"{kind}: {message}"[:300]
        if kind in {"auth", "forbidden"}:
            record["disabled"] = True
        elif kind == "rate_limit":
            record["cooldown_until"] = (utc_now() + timedelta(days=1)).replace(
                hour=0, minute=5, second=0, microsecond=0
            ).isoformat()
        elif kind in {"server", "timeout"}:
            record["cooldown_until"] = (utc_now() + timedelta(minutes=30)).isoformat()
        self.save()

    def save(self) -> None:
        atomic_json(self.path, self.state)

    def public_status(self) -> dict[str, Any]:
        return {
            "updated_at": utc_now().isoformat(),
            "providers": {
                name: {
                    "requests": row["requests"],
                    "soft_limit": self.limits.get(name, 30 if name.startswith("rss_") else 0),
                    "available": self.available(name),
                    "cooldown_until": row["cooldown_until"],
                    "last_error": row["last_error"],
                }
                for name, row in self.state["providers"].items()
            },
        }


def request_json(
    session: requests.Session,
    quota: QuotaManager,
    provider: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 25,
) -> Any:
    if not quota.available(provider):
        raise ProviderError(provider, "quota", f"{provider} is unavailable for this run")
    last_error: Exception | None = None
    for attempt in range(3):
        if not quota.available(provider):
            break
        quota.requested(provider)
        try:
            response = session.get(url, params=params, headers=headers, timeout=timeout)
            if response.status_code in {401, 403}:
                raise ProviderError(provider, "auth", f"HTTP {response.status_code}")
            if response.status_code == 429:
                raise ProviderError(provider, "rate_limit", "HTTP 429")
            if response.status_code >= 500:
                raise ProviderError(provider, "server", f"HTTP {response.status_code}")
            response.raise_for_status()
            return response.json()
        except ProviderError as error:
            quota.failed(provider, error.kind, str(error))
            last_error = error
            if error.kind not in {"server"}:
                break
        except requests.Timeout as error:
            quota.failed(provider, "timeout", str(error))
            last_error = error
        except requests.RequestException as error:
            quota.failed(provider, "network", str(error))
            last_error = error
            break
        time.sleep(2 ** attempt)
    raise ProviderError(provider, "failed", str(last_error or "request failed"))


def normalized_article(
    provider: str, title: str, description: str, url: str, category: str,
    published: str | None, *, author: str = "", content_type: str = "news",
    image_url: str = "", thai_demo: str = "",
) -> dict[str, Any] | None:
    title, description = normalize(title), normalize(description)
    if not title or len(description.split()) < 18 or not url:
        return None
    return {
        "id": stable_id(provider, url, title), "provider": provider, "title": title,
        "description": description, "url": url, "category": category.title(),
        "published": parse_date(published).isoformat(), "author": normalize(author),
        "content_type": content_type, "image_url": image_url, "thai_demo": thai_demo,
    }


def demo_articles() -> list[dict[str, Any]]:
    now = utc_now().isoformat()
    rows = [
        normalized_article(
            "demo", title, description, f"https://example.com/{identifier}", category, now,
            author="Demo Learning Desk", content_type="educational demo", thai_demo=thai,
        )
        for identifier, title, category, description, thai in DEMO_TOPICS
    ]
    extras = [
        ("demo-food", "School kitchens test healthier lunch menus", "Health",
         "Several schools are testing healthier lunch menus this month. The meals use more fresh vegetables and less added sugar. Teachers say students are trying new foods and talking about nutrition in class."),
        ("demo-train", "City adds evening trains for busy commuters", "Business",
         "The city is adding more evening trains on its busiest route. Transit staff say the change should reduce crowding after work. The schedule will be reviewed after three months."),
        ("demo-forest", "Volunteers plant trees near a restored river", "Environment",
         "Community volunteers planted new trees near a restored river. The trees will provide shade and help protect the soil. Local groups will water the young trees during dry weeks."),
        ("demo-space", "New telescope images help students study stars", "Science",
         "A new set of telescope images is helping students study stars and galaxies. Teachers can use the free images in science lessons. Researchers hope the project will make space science easier to understand."),
    ]
    for identifier, title, category, description in extras:
        if len([row for row in rows if row]) >= DAILY_ARTICLE_COUNT:
            break
        rows.append(normalized_article(
            "demo", title, description, f"https://example.com/{identifier}", category, now,
            author="Demo Learning Desk", content_type="educational demo", thai_demo="คำแปลภาษาไทยสำหรับบทความตัวอย่าง",
        ))
    return [row for row in rows if row]


def fetch_currents(session: requests.Session, quota: QuotaManager, config: dict[str, Any]) -> list[dict[str, Any]]:
    key = config["currents_key"]
    if not key:
        return []
    payload = request_json(session, quota, "currents", CURRENTS_URL, params={
        "language": "en", "page_size": 30, "apiKey": key,
    }, timeout=config["timeout"])
    return [item for row in payload.get("news", []) if (item := normalized_article(
        "Currents", row.get("title", ""), row.get("description", ""), row.get("url", ""),
        (row.get("category") or ["World"])[0] if isinstance(row.get("category"), list) else row.get("category", "World"),
        row.get("published"), author=row.get("author", ""),
    ))]


def fetch_guardian(session: requests.Session, quota: QuotaManager, config: dict[str, Any]) -> list[dict[str, Any]]:
    key = config["guardian_key"]
    if not key:
        return []
    payload = request_json(session, quota, "guardian", GUARDIAN_URL, params={
        "api-key": key, "page-size": 30, "order-by": "newest", "show-fields": "trailText,bodyText,thumbnail",
    }, timeout=config["timeout"])
    articles = []
    for row in payload.get("response", {}).get("results", []):
        fields = row.get("fields", {})
        text = fields.get("bodyText") or fields.get("trailText", "")
        item = normalized_article(
            "The Guardian", row.get("webTitle", ""), text, row.get("webUrl", ""),
            row.get("sectionName", "World"), row.get("webPublicationDate"),
            content_type="news", image_url=fields.get("thumbnail", ""),
        )
        if item:
            articles.append(item)
    return articles


def fetch_rss(session: requests.Session, quota: QuotaManager, config: dict[str, Any]) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    for provider, category, url in RSS_FEEDS:
        quota_name = f"rss_{slugify(provider + '-' + category, 24)}"
        if not quota.available(quota_name):
            continue
        quota.requested(quota_name)
        try:
            response = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=config["timeout"])
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except (requests.RequestException, ET.ParseError) as error:
            quota.failed(quota_name, "network", str(error))
            logging.warning("%s RSS unavailable: %s", provider, error)
            continue

        for node in root.iter():
            if xml_name(node.tag) not in {"item", "entry"}:
                continue
            title = child_text(node, "title")
            description = (
                child_text(node, "description", "summary", "content", "encoded")
                or child_text(node, "subtitle")
            )
            link = child_text(node, "link")
            if not link:
                link = child_attr(node, "link", "href")
            published = child_text(node, "pubDate", "published", "updated", "dc:date")
            image_url = (
                child_attr(node, "thumbnail", "url")
                or child_attr(node, "content", "url")
                or child_attr(node, "enclosure", "url")
            )
            item = normalized_article(
                provider, title, description, link, category, published,
                author=provider, content_type="rss news summary", image_url=image_url,
            )
            if item:
                articles.append(item)
    return articles


def fetch_nasa(session: requests.Session, quota: QuotaManager, config: dict[str, Any]) -> list[dict[str, Any]]:
    payload = request_json(session, quota, "nasa", NASA_APOD_URL, params={
        "api_key": config["nasa_key"], "count": 3,
    }, timeout=config["timeout"])
    rows = payload if isinstance(payload, list) else [payload]
    return [item for row in rows if (item := normalized_article(
        "NASA", row.get("title", ""), row.get("explanation", ""),
        row.get("hdurl") or row.get("url", ""), "Science", row.get("date"),
        author=row.get("copyright", "NASA"), content_type="agency science report",
        image_url=row.get("url", "") if row.get("media_type") == "image" else "",
    ))]


def fetch_nws(session: requests.Session, quota: QuotaManager, config: dict[str, Any]) -> list[dict[str, Any]]:
    payload = request_json(session, quota, "nws", NWS_ALERTS_URL, params={"status": "actual", "limit": 20},
                           headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
                           timeout=config["timeout"])
    articles = []
    for feature in payload.get("features", [])[:10]:
        row = feature.get("properties", {})
        item = normalized_article(
            "US National Weather Service", row.get("headline") or row.get("event", ""),
            row.get("description", ""), row.get("@id") or feature.get("id", ""),
            "Environment", row.get("sent"), author="National Weather Service",
            content_type="government weather alert",
        )
        if item:
            articles.append(item)
    return articles


def fetch_usgs(session: requests.Session, quota: QuotaManager, config: dict[str, Any]) -> list[dict[str, Any]]:
    payload = request_json(session, quota, "usgs", USGS_URL, timeout=config["timeout"])
    articles = []
    for feature in payload.get("features", [])[:10]:
        row = feature.get("properties", {})
        magnitude = row.get("mag")
        description = (
            f"The United States Geological Survey reported an earthquake of magnitude {magnitude}. "
            f"The event occurred near {row.get('place', 'an identified location')}. "
            "Official monitoring data may be updated as scientists review additional measurements."
        )
        item = normalized_article(
            "USGS", row.get("title", ""), description, row.get("url", ""), "World",
            datetime.fromtimestamp((row.get("time") or 0) / 1000, timezone.utc).isoformat(),
            author="U.S. Geological Survey", content_type="government earthquake report",
        )
        if item:
            articles.append(item)
    return articles


def fetch_arxiv(session: requests.Session, quota: QuotaManager, config: dict[str, Any]) -> list[dict[str, Any]]:
    if not quota.available("arxiv"):
        return []
    quota.requested("arxiv")
    try:
        response = session.get(ARXIV_URL, params={
            "search_query": "cat:cs.AI OR cat:cs.CL OR cat:cs.RO",
            "start": 0, "max_results": 12, "sortBy": "submittedDate", "sortOrder": "descending",
        }, timeout=config["timeout"])
        response.raise_for_status()
    except requests.RequestException as error:
        quota.failed("arxiv", "network", str(error))
        raise ProviderError("arxiv", "failed", str(error)) from error
    root = ET.fromstring(response.text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    articles = []
    for entry in root.findall("atom:entry", ns):
        item = normalized_article(
            "arXiv", entry.findtext("atom:title", "", ns), entry.findtext("atom:summary", "", ns),
            entry.findtext("atom:id", "", ns), "Technology", entry.findtext("atom:published", "", ns),
            author=", ".join(node.findtext("atom:name", "", ns) for node in entry.findall("atom:author", ns)),
            content_type="research summary",
        )
        if item:
            articles.append(item)
    return articles


def collect_candidates(session: requests.Session, quota: QuotaManager, config: dict[str, Any]) -> list[dict[str, Any]]:
    if config["demo"]:
        return demo_articles()
    providers: list[tuple[str, Callable[..., list[dict[str, Any]]]]] = [
        ("rss", fetch_rss), ("currents", fetch_currents), ("guardian", fetch_guardian), ("nasa", fetch_nasa),
        ("nws", fetch_nws), ("usgs", fetch_usgs), ("arxiv", fetch_arxiv),
    ]
    results: list[dict[str, Any]] = []
    for name, fetcher in providers:
        try:
            batch = fetcher(session, quota, config)
            logging.info("%s supplied %d candidate(s)", name, len(batch))
            results.extend(batch)
        except ProviderError as error:
            logging.warning("%s unavailable: %s", name, error)
    unique: dict[str, dict[str, Any]] = {}
    for article in results:
        unique.setdefault(article["id"], article)
    return list(unique.values())


def complexity(text: str) -> float:
    sentences = sentence_split(text) or [text]
    words = re.findall(r"[A-Za-z]+", text)
    long_words = sum(len(word) >= 8 for word in words)
    return len(words) / max(1, len(sentences)) + long_words / max(1, len(words)) * 20


def choose_daily_articles(candidates: list[dict[str, Any]], offset: int = 0) -> list[dict[str, Any]]:
    candidates = sorted(candidates, key=lambda row: complexity(row["description"]))
    if len(candidates) < DAILY_ARTICLE_COUNT:
        return []
    if offset:
        shift = offset % len(candidates)
        candidates = candidates[shift:] + candidates[:shift]
    midpoint = len(candidates) // 2
    upper = max(midpoint + 2, int(len(candidates) * 0.72))
    indexes = {
        "A1": [0, 1],
        "A2": [2, 3],
        "B1": [max(4, midpoint - 1), midpoint],
        "B2": [min(len(candidates) - 3, upper), min(len(candidates) - 2, upper + 1)],
        "C1": [len(candidates) - 2, len(candidates) - 1],
    }
    chosen: list[dict[str, Any]] = []
    used: set[str] = set()
    for level in LEVELS:
        preferred = indexes[level]
        pool = preferred + list(range(len(candidates)))
        for index in pool:
            article = candidates[index]
            if article["id"] in used:
                continue
            row = dict(article)
            row["level"] = level
            chosen.append(row)
            used.add(article["id"])
            if sum(item["level"] == level for item in chosen) == TARGET_PER_LEVEL:
                break
    return chosen if len(chosen) == DAILY_ARTICLE_COUNT else []


def summarize(text: str) -> str:
    text = clean_story_text(text)
    sentences = sentence_split(text)
    if len(sentences) <= 6 or len(text.split()) < 120:
        return " ".join(sentences[:6])
    try:
        result = normalize(textrank_summarize(text, ratio=0.5, words=320))
    except ValueError:
        result = ""
    return result or " ".join(sentences[:5])


def simplify_sentence(sentence: str, max_words: int, aggressive: bool) -> list[str]:
    for hard, easy in SIMPLE_REPLACEMENTS.items():
        sentence = re.sub(rf"\b{hard}\b", easy, sentence, flags=re.I)
    sentence = re.sub(r"\s*[;:—]\s*", ". ", sentence)
    if aggressive:
        sentence = re.sub(r",?\s+(which|who|although|however|while)\s+", ". ", sentence, flags=re.I)
    output = []
    for piece in sentence_split(sentence) or [sentence]:
        words = piece.split()
        while words:
            if len(words) <= max_words + 4:
                chunk, words = words, []
            else:
                lower_bound = max(5, max_words - 4)
                upper_bound = min(len(words), max_words + 3)
                breakpoint = next(
                    (
                        index for index in range(upper_bound, lower_bound - 1, -1)
                        if words[index - 1].lower().strip(",") in {"and", "but", "so", "because", "while"}
                    ),
                    max_words,
                )
                chunk, words = words[:breakpoint], words[breakpoint:]
            text = " ".join(chunk).strip(" ,")
            if text:
                output.append(text[0].upper() + text[1:] + ("" if text[-1] in ".!?" else "."))
    return output


def adapt_level(text: str, level: str, config: dict[str, Any], session: requests.Session) -> str:
    summary = summarize(text)
    if config["ollama_url"]:
        try:
            prompt = (
                f"Rewrite only the facts below as CEFR {level} English. Do not add facts. "
                "Return plain text only.\n\n" + summary
            )
            response = session.post(
                f"{config['ollama_url'].rstrip('/')}/api/generate",
                json={"model": config["ollama_model"], "prompt": prompt, "stream": False},
                timeout=config["timeout"] * 3,
            )
            response.raise_for_status()
            generated = normalize(response.json().get("response", ""))
            if len(generated.split()) >= 35:
                return clean_story_text(generated)
        except requests.RequestException:
            logging.warning("Ollama unavailable; using deterministic level adapter")
    sentences = sentence_split(clean_story_text(summary))
    _, max_words = sentence_budget(level)
    if level == "A1":
        parts = [part for sentence in sentences[:5] for part in simplify_sentence(sentence, 8, True)]
        return trim_to_word_budget(parts[:10], max_words)
    if level == "A2":
        parts = [part for sentence in sentences[:6] for part in simplify_sentence(sentence, 12, True)]
        return trim_to_word_budget(parts[:12], max_words)
    if level == "B1":
        parts = [part for sentence in sentences[:8] for part in simplify_sentence(sentence, 18, False)]
        return trim_to_word_budget(parts[:12], max_words)
    if level == "B2":
        return trim_to_word_budget(sentences[:9], max_words)
    return trim_to_word_budget(sentences[:11], max_words)


def vocabulary_words(text: str) -> list[str]:
    words = [word.lower().strip("'") for word in re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", text)]
    return sorted({word for word in words if word})


def part_of_speech(word: str) -> str:
    key = word.lower().strip("'")
    if key in DETERMINERS:
        return "det."
    if key in PRONOUNS:
        return "pron."
    if key in PREPOSITIONS:
        return "prep."
    if key in CONJUNCTIONS:
        return "conj."
    if key in COMMON_VERBS:
        return "v."
    if key in COMMON_ADJECTIVES:
        return "adj."
    if key.endswith("ly"):
        return "adv."
    if key.endswith(("tion", "sion", "ment", "ness", "ity", "ship", "er", "or", "ist")):
        return "n."
    if key.endswith(("able", "ible", "al", "ful", "ic", "ive", "less", "ous")):
        return "adj."
    if key.endswith(("ate", "en", "ify", "ise", "ize")):
        return "v."
    if key.endswith(("ed", "ing")):
        return "v."
    if key.endswith("s") and len(key) > 3:
        return "n."
    return "n."


class Translator:
    def __init__(self, session: requests.Session, config: dict[str, Any]) -> None:
        self.session, self.config = session, config
        self.cache = load_json(TRANSLATION_CACHE_PATH, {})

    def translate(self, text: str, words: list[str], demo_thai: str = "") -> tuple[str, dict[str, str]]:
        key = hashlib.sha256(text.encode()).hexdigest()
        if key in self.cache and all(word in self.cache[key].get("words", {}) for word in words):
            row = self.cache[key]
            if not re.search(r"เธ|เน|โ€", row.get("thai_text", "")):
                return row["thai_text"], safe_word_translations(words, row.get("words", {}))
        if self.config["demo"]:
            dictionary = safe_word_translations(words)
            result = (demo_thai or "คำแปลภาษาไทยสำหรับบทความตัวอย่าง", dictionary)
            self.cache[key] = {"thai_text": result[0], "words": result[1]}
            atomic_json(TRANSLATION_CACHE_PATH, self.cache)
            return result
        payload: dict[str, Any] = {"q": [text, *words], "source": "en", "target": "th", "format": "text"}
        if self.config["libre_key"]:
            payload["api_key"] = self.config["libre_key"]
        translated: list[str] | None = None
        try:
            response = self.session.post(
                f"{self.config['libre_url'].rstrip('/')}/translate",
                json=payload, timeout=self.config["timeout"] * 2,
            )
            response.raise_for_status()
            value = response.json().get("translatedText")
            translated = [value] if isinstance(value, str) else value
        except requests.RequestException:
            translated = self._argos([text, *words])
        if not translated or len(translated) != len(words) + 1:
            result = ("", safe_word_translations(words))
        else:
            result = (
                normalize(translated[0]),
                safe_word_translations(words, {word: normalize(value) for word, value in zip(words, translated[1:])}),
            )
        self.cache[key] = {"thai_text": result[0], "words": result[1]}
        atomic_json(TRANSLATION_CACHE_PATH, self.cache)
        return result

    @staticmethod
    def _argos(values: list[str]) -> list[str] | None:
        try:
            import argostranslate.translate  # type: ignore
            languages = argostranslate.translate.get_installed_languages()
            source = next(language for language in languages if language.code == "en")
            target = next(language for language in languages if language.code == "th")
            translation = source.get_translation(target)
            return [translation.translate(value) for value in values]
        except (ImportError, StopIteration, AttributeError):
            return None


def image_for(
    article: dict[str, Any], session: requests.Session, quota: QuotaManager, config: dict[str, Any],
) -> dict[str, str]:
    cache = load_json(IMAGE_CACHE_PATH, {})
    if article["id"] in cache:
        cached = cache[article["id"]]
        local_name = cached.get("local_filename")
        if local_name and (STATIC_DIR / "images" / local_name).exists():
            return cached
        if not cached.get("url"):
            return {"local_filename": "news-fallback.svg", "credit": "Local fallback", "credit_url": ""}
    if config["demo"]:
        filename = DEMO_IMAGE_MAP.get(article["title"], "demo-solar-library.png")
        result = {"local_filename": filename, "credit": "Generated demo image", "credit_url": ""}
        cache[article["id"]] = result
        atomic_json(IMAGE_CACHE_PATH, cache)
        return result
    if config["local_image_url"]:
        try:
            endpoint = f"{config['local_image_url'].rstrip('/')}/sdapi/v1/txt2img"
            prompt = (
                f"Realistic editorial news photograph about {article['title']}. "
                f"Context: {article['description'][:400]}. "
                "Natural light, documentary photography, accurate real-world details, "
                "landscape composition, no text, no logo, no watermark."
            )
            response = session.post(endpoint, json={
                "prompt": prompt,
                "negative_prompt": (
                    "text, caption, logo, watermark, poster, illustration, cartoon, "
                    "distorted hands, duplicate people, blurry"
                ),
                "width": 1024,
                "height": 576,
                "steps": config["local_image_steps"],
            }, timeout=config["local_image_timeout"])
            response.raise_for_status()
            encoded = (response.json().get("images") or [])[0].split(",", 1)[-1]
            image_bytes = base64.b64decode(encoded, validate=True)
            if len(image_bytes) < 10_000:
                raise ValueError("Local image response was too small")
            filename = f"generated-{article['id']}.png"
            output = STATIC_DIR / "images" / filename
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(image_bytes)
            result = {
                "local_filename": filename,
                "credit": "Generated locally with Stable Diffusion",
                "credit_url": "",
            }
            cache[article["id"]] = result
            atomic_json(IMAGE_CACHE_PATH, cache)
            return result
        except (requests.RequestException, ValueError, KeyError, IndexError, json.JSONDecodeError) as error:
            logging.warning("Local image generator unavailable for %s: %s", article["title"], error)
    if article.get("image_url"):
        result = {
            "url": article["image_url"], "credit": article["provider"], "credit_url": article["url"],
        }
        result = cache_image_or_fallback(article, result, session, config)
        cache[article["id"]] = result
        atomic_json(IMAGE_CACHE_PATH, cache)
        return result
    query = " ".join(re.findall(r"[A-Za-z]{4,}", article["title"])[:6])
    result_page = 1 + (int(article["id"][:4], 16) % 5)
    result: dict[str, str] | None = None
    if config["unsplash_key"]:
        try:
            payload = request_json(session, quota, "unsplash", UNSPLASH_URL, params={
                "query": query, "per_page": 1, "page": result_page, "orientation": "landscape",
            }, headers={"Authorization": f"Client-ID {config['unsplash_key']}", "Accept-Version": "v1"},
                timeout=config["timeout"])
            photo = (payload.get("results") or [])[0]
            user = photo.get("user", {})
            result = {
                "url": add_query(photo["urls"]["raw"], {"w": "1400", "h": "800", "fit": "crop", "q": "78"}),
                "credit": user.get("name", "Unsplash contributor"),
                "credit_url": add_query(user.get("links", {}).get("html", "https://unsplash.com"), {
                    "utm_source": "daily_english_reader", "utm_medium": "referral",
                }),
            }
        except (ProviderError, IndexError, KeyError):
            result = None
    if not result:
        try:
            payload = request_json(session, quota, "openverse", OPENVERSE_URL, params={
                "q": query, "page_size": 1, "page": result_page, "license_type": "commercial",
            }, timeout=config["timeout"])
            image = (payload.get("results") or [])[0]
            result = {
                "url": image.get("url") or image.get("thumbnail", ""),
                "credit": image.get("creator") or "Openverse contributor",
                "credit_url": image.get("foreign_landing_url") or "https://openverse.org/",
            }
        except (ProviderError, IndexError):
            result = None
    if not result:
        try:
            payload = request_json(session, quota, "commons", COMMONS_URL, params={
                "action": "query", "generator": "search", "gsrsearch": query, "gsrnamespace": 6,
                "gsrlimit": 1, "prop": "imageinfo", "iiprop": "url|extmetadata", "format": "json",
            }, timeout=config["timeout"])
            page = next(iter(payload.get("query", {}).get("pages", {}).values()))
            info = page["imageinfo"][0]
            result = {
                "url": info["url"], "credit": "Wikimedia Commons contributor",
                "credit_url": info.get("descriptionurl", "https://commons.wikimedia.org/"),
            }
        except (ProviderError, StopIteration, KeyError):
            result = None
    if not result:
        result = {"local_filename": "demo-solar-library.png", "credit": "Local fallback", "credit_url": ""}
    result = cache_image_or_fallback(article, result, session, config)
    cache[article["id"]] = result
    atomic_json(IMAGE_CACHE_PATH, cache)
    return result


def cache_image_or_fallback(
    article: dict[str, Any], result: dict[str, str], session: requests.Session, config: dict[str, Any],
) -> dict[str, str]:
    if result.get("local_filename"):
        return result
    url = result.get("url", "")
    if not url:
        return {"local_filename": "news-fallback.svg", "credit": "Local fallback", "credit_url": ""}
    try:
        response = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=config["timeout"])
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "image" not in content_type or len(response.content) < 1000:
            raise ValueError("not a usable image")
        suffix = ".png" if "png" in content_type else ".webp" if "webp" in content_type else ".jpg"
        filename = f"news-{article['id'][:12]}{suffix}"
        output = STATIC_DIR / "images" / filename
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(response.content)
        return {
            "local_filename": filename,
            "credit": result.get("credit", article["provider"]),
            "credit_url": result.get("credit_url", article["url"]),
        }
    except (requests.RequestException, ValueError, OSError) as error:
        logging.info("Image cache failed for %s: %s", article["title"], error)
        return {"local_filename": "news-fallback.svg", "credit": "Local fallback", "credit_url": ""}


def source_material(raw: dict[str, Any], session: requests.Session, config: dict[str, Any]) -> str:
    """Use source-page paragraphs when available, otherwise keep the feed summary."""
    fallback = raw["description"]
    if config["demo"]:
        return fallback
    try:
        response = session.get(raw["url"], headers={"User-Agent": USER_AGENT}, timeout=config["timeout"])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for selector in ("script", "style", "nav", "header", "footer", "aside", "form"):
            for node in soup.select(selector):
                node.decompose()
        paragraphs = []
        for node in soup.select("article p, main p, [role='main'] p, p"):
            text = normalize(node.get_text(" "))
            if len(text.split()) >= 8 and not re.search(r"\b(subscribe|sign up|cookie|newsletter)\b", text, re.I):
                paragraphs.append(text)
            if sum(len(row.split()) for row in paragraphs) >= 420:
                break
        material = " ".join(paragraphs)
        if len(material.split()) >= 80:
            return material
    except requests.RequestException as error:
        logging.info("Source-page text unavailable for %s: %s", raw["title"], error)
    return fallback


def naturalize_thai(text: str) -> str:
    text = normalize(text)
    replacements = {
        "ได้กล่าวว่า": "บอกว่า",
        "กล่าวว่า": "บอกว่า",
        "ประชาชน": "ผู้คน",
        "สามารถ": "ทำได้",
        "เนื่องจาก": "เพราะ",
        "อย่างไรก็ตาม": "แต่",
        "ในขณะที่": "ขณะที่",
        "ดังกล่าว": "นี้",
        "รายงานว่า": "รายงานว่า",
    }
    for formal, natural in replacements.items():
        text = text.replace(formal, natural)
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def generate_audio(text: str, article_id: str, level: str, date: str, config: dict[str, Any]) -> Path:
    output_dir = AUDIO_CACHE_DIR / date
    output_dir.mkdir(parents=True, exist_ok=True)
    if config["skip_audio"]:
        demo_output = output_dir / f"{article_id}-{level.lower()}.wav"
        if not demo_output.exists():
            with wave.open(str(demo_output), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(22050)
                audio.writeframes(b"\x00\x00" * 22050)
        return demo_output
    output = output_dir / f"{article_id}-{level.lower()}.mp3"
    if output.exists() and output.stat().st_size > 1000:
        return output
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")
    if config.get("tts_provider") == "edge":
        try:
            voice = {
                "A1": "en-US-JennyNeural",
                "A2": "en-US-JennyNeural",
                "B1": "en-US-AriaNeural",
                "B2": "en-US-GuyNeural",
                "C1": "en-US-GuyNeural",
            }[level]
            rate = {"A1": "-18%", "A2": "-12%", "B1": "-6%", "B2": "+0%", "C1": "+4%"}[level]
            subprocess.run([
                sys.executable, "-m", "edge_tts",
                "--voice", voice, f"--rate={rate}", "--text", text,
                "--write-media", str(output),
            ], check=True, capture_output=True, timeout=90)
            if output.exists() and output.stat().st_size > 400:
                return output
        except (subprocess.SubprocessError, OSError) as error:
            logging.warning("edge-tts unavailable; falling back to local TTS: %s", error)
    wav = output.with_suffix(".wav")
    local_rates = {"A1": 132, "A2": 145, "B1": 160, "B2": 172, "C1": 182}
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", local_rates[level])
        engine.save_to_file(text, str(wav))
        engine.runAndWait()
        engine.stop()
    except Exception:
        wav.unlink(missing_ok=True)
    if not wav.exists() or wav.stat().st_size < 100:
        espeak = shutil.which("espeak-ng") or shutil.which("espeak")
        if not espeak:
            raise RuntimeError("pyttsx3 and espeak-ng both failed")
        subprocess.run([espeak, "-s", str(local_rates[level]), "-w", str(wav), text],
                       check=True, capture_output=True)
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(wav), "-codec:a", "libmp3lame", "-q:a", "5", str(output)],
                   check=True)
    wav.unlink(missing_ok=True)
    if output.stat().st_size < 400:
        raise RuntimeError("Generated MP3 is invalid")
    return output


def process_article(
    raw: dict[str, Any], session: requests.Session, quota: QuotaManager,
    translator: Translator, config: dict[str, Any], published_date: str,
) -> dict[str, Any]:
    material = source_material(raw, session, config)
    text = adapt_level(material, raw["level"], config, session)
    words = vocabulary_words(text)
    thai_text, translations = translator.translate(text, words, raw.get("thai_demo", ""))
    thai_text = naturalize_thai(thai_text)
    thai_text = natural_thai_article(raw, text)
    translations = safe_word_translations(words, translations)
    word_pos = {word: part_of_speech(word) for word in words}
    audio_path = generate_audio(text, raw["id"], raw["level"], published_date, config)
    image = image_for(raw, session, quota, config)
    slug = f"{slugify(raw['title'])}-{raw['id'][:8]}"
    return {
        "schema_version": SCHEMA_VERSION, "id": raw["id"], "slug": slug, "level": raw["level"],
        "title": raw["title"], "description": raw["description"], "text": text, "thai_text": thai_text,
        "word_translations": translations, "category": raw["category"], "provider": raw["provider"],
        "word_pos": word_pos,
        "content_type": raw["content_type"], "source_url": raw["url"], "author": raw["author"],
        "published": raw["published"], "published_date": published_date, "image": image,
        "audio_cache_path": str(audio_path.relative_to(ROOT)).replace("\\", "/"),
        "generated_at": utc_now().isoformat(),
    }


def word_spans(text: str, translations: dict[str, str], word_pos: dict[str, str] | None = None) -> Markup:
    pieces = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*|[^A-Za-z]+", text)
    output = []
    for piece in pieces:
        if re.fullmatch(r"[A-Za-z]+(?:['-][A-Za-z]+)*", piece):
            key = piece.lower()
            output.append(
                f'<span class="word" tabindex="0" role="button" data-word="{html.escape(piece, quote=True)}" '
                f'data-translation="{html.escape(translations.get(key, ""), quote=True)}" '
                f'data-pos="{html.escape((word_pos or {}).get(key, part_of_speech(key)), quote=True)}">'
                f'{html.escape(piece)}</span>'
            )
        else:
            output.append(html.escape(piece))
    return Markup("".join(output))


def load_articles(retention_days: int) -> list[dict[str, Any]]:
    cutoff = utc_now() - timedelta(days=retention_days)
    articles = []
    for path in PROCESSED_DIR.glob("*/*.json"):
        row = load_json(path, None)
        if row and row.get("schema_version") == SCHEMA_VERSION and parse_date(row.get("generated_at")) >= cutoff:
            articles.append(row)
    return sorted(articles, key=lambda row: parse_date(row["generated_at"]), reverse=True)


def article_view(article: dict[str, Any], base_prefix: str) -> dict[str, Any]:
    audio_source = ROOT / article["audio_cache_path"]
    image = article["image"]
    image_url = (
        f"{base_prefix}static/images/{image['local_filename']}"
        if image.get("local_filename")
        else image.get("url", "")
    )
    return {
        **article,
        "page_url": f"{base_prefix}news/{article['published_date']}/{article['slug']}/index.html",
        "image_url": image_url,
        "published_display": parse_date(article["published"]).strftime("%d %b %Y"),
        "word_html": word_spans(article["text"], article["word_translations"], article.get("word_pos", {})),
        "audio_source": audio_source,
    }


def render_site(articles: list[dict[str, Any]], quota: QuotaManager) -> None:
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    shutil.copytree(STATIC_DIR, STAGING_DIR / "static")
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html"]))
    common = {
        "description": "Free daily English news practice for Thai learners.",
        "updated_at": utc_now().astimezone().strftime("%d %b %Y, %H:%M"),
    }
    views = [article_view(article, "") for article in articles]
    today = utc_now().date().isoformat()
    recent_cutoff = utc_now().date() - timedelta(days=6)
    recent = [row for row in views if parse_date(row["published_date"]).date() >= recent_cutoff]
    today_views = [row for row in views if row["published_date"] == today]
    available_dates = sorted({row["published_date"] for row in recent}, reverse=True)[:7]
    home_days = []
    for date in available_dates:
        day_articles = [row for row in recent if row["published_date"] == date]
        home_days.append({
            "date": date,
            "date_display": parse_date(date).strftime("%d %b %Y"),
            "label": "Today" if date == today else parse_date(date).strftime("%A"),
            "articles": day_articles,
            "featured": day_articles[0] if day_articles else None,
            "level_groups": {
                level: [row for row in day_articles if row["level"] == level]
                for level in LEVELS
            },
        })
    index = env.get_template("index.html").render(
        **common, page_title="Read English Daily", page_type="index", base_prefix="",
        home_days=home_days, available_levels=LEVELS,
    )
    daily = env.get_template("daily.html").render(
        **common, page_title="Daily Reading", page_type="daily", base_prefix="", articles=recent,
        available_levels=LEVELS,
    )
    vocabulary = env.get_template("vocabulary.html").render(
        **common, page_title="Vocabulary", page_type="vocabulary", base_prefix="",
    )
    flashcards = env.get_template("flashcards.html").render(
        **common, page_title="Flashcards", page_type="flashcards", base_prefix="",
    )
    saved = env.get_template("saved.html").render(
        **common, page_title="Saved News", page_type="saved", base_prefix="",
    )
    (STAGING_DIR / "index.html").write_text(index, encoding="utf-8")
    (STAGING_DIR / "daily.html").write_text(daily, encoding="utf-8")
    (STAGING_DIR / "vocabulary.html").write_text(vocabulary, encoding="utf-8")
    (STAGING_DIR / "flashcards.html").write_text(flashcards, encoding="utf-8")
    (STAGING_DIR / "saved.html").write_text(saved, encoding="utf-8")

    content_index = []
    article_template = env.get_template("article.html")
    for article in articles:
        directory = STAGING_DIR / "news" / article["published_date"] / article["slug"]
        directory.mkdir(parents=True, exist_ok=True)
        view = article_view(article, "../../../")
        audio_filename = f"{article['level'].lower()}{view['audio_source'].suffix}"
        shutil.copy2(view["audio_source"], directory / audio_filename)
        view["audio_url"] = audio_filename
        view["page_url"] = f"../../../news/{article['published_date']}/{article['slug']}/index.html"
        page = article_template.render(
            **common, page_title=f"{article['title']} | Read English Daily",
            page_type="article", base_prefix="../../../", article=view,
        )
        (directory / "index.html").write_text(page, encoding="utf-8")
        public_json = {key: value for key, value in article.items() if key != "audio_cache_path"}
        atomic_json(directory / "article.json", public_json)
        content_index.append({
            "id": article["id"], "title": article["title"],
            "url": f"news/{article['published_date']}/{article['slug']}/index.html",
            "level": article["level"], "category": article["category"],
            "date": article["published_date"],
            "image": article_view(article, "")["image_url"],
        })
    atomic_json(STAGING_DIR / "content-index.json", content_index)
    atomic_json(STAGING_DIR / "provider-status.json", quota.public_status())
    validate_staging(today_views)
    atomic_publish()


def validate_staging(today_articles: list[dict[str, Any]]) -> None:
    if len(today_articles) != DAILY_ARTICLE_COUNT:
        raise RuntimeError(f"Expected {DAILY_ARTICLE_COUNT} current articles, got {len(today_articles)}")
    if Counter(row["level"] for row in today_articles) != Counter({level: TARGET_PER_LEVEL for level in LEVELS}):
        raise RuntimeError("Current articles are not split 2 per level")
    required = ["index.html", "daily.html", "vocabulary.html", "flashcards.html", "saved.html", "content-index.json"]
    if any(not (STAGING_DIR / name).exists() for name in required):
        raise RuntimeError("Staging site is incomplete")
    for article in today_articles:
        directory = STAGING_DIR / "news" / article["published_date"] / article["slug"]
        if not (directory / "index.html").exists() or not (directory / "article.json").exists():
            raise RuntimeError(f"Missing output for {article['id']}")
        audio_files = list(directory.glob(f"{article['level'].lower()}.*"))
        if not audio_files:
            raise RuntimeError(f"Missing audio for {article['id']}")
        if article.get("provider") != "demo":
            mp3 = directory / f"{article['level'].lower()}.mp3"
            if not mp3.exists() or mp3.stat().st_size < 400:
                raise RuntimeError(f"Missing production MP3 audio for {article['id']}")


def atomic_publish() -> None:
    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR)
    if SITE_DIR.exists():
        SITE_DIR.replace(BACKUP_DIR)
    try:
        STAGING_DIR.replace(SITE_DIR)
    except Exception:
        if BACKUP_DIR.exists() and not SITE_DIR.exists():
            BACKUP_DIR.replace(SITE_DIR)
        raise
    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR)


def cleanup(retention_days: int) -> None:
    cutoff = utc_now().date() - timedelta(days=retention_days)
    for base in (RAW_DIR, PROCESSED_DIR, AUDIO_CACHE_DIR, QUOTA_DIR):
        if not base.exists():
            continue
        for path in base.iterdir():
            date_text = path.name[:10]
            try:
                old = datetime.fromisoformat(date_text).date() < cutoff
            except ValueError:
                old = False
            if old:
                shutil.rmtree(path) if path.is_dir() else path.unlink(missing_ok=True)


def is_demo_edition(articles: list[dict[str, Any]]) -> bool:
    return bool(articles) and all(row.get("provider") == "demo" for row in articles)


def purge_demo_editions() -> None:
    for output_dir in PROCESSED_DIR.iterdir() if PROCESSED_DIR.exists() else []:
        if not output_dir.is_dir():
            continue
        rows = [load_json(path, None) for path in output_dir.glob("*.json")]
        articles = [row for row in rows if isinstance(row, dict)]
        if is_demo_edition(articles):
            date_text = output_dir.name
            logging.info("Removing demo-only Reading edition for %s", date_text)
            shutil.rmtree(output_dir)
            audio_dir = AUDIO_CACHE_DIR / date_text
            if audio_dir.exists():
                shutil.rmtree(audio_dir)
            raw_file = RAW_DIR / f"{date_text}-providers.json"
            raw_file.unlink(missing_ok=True)


def config_from_env() -> dict[str, Any]:
    if not env_bool("FREE_ONLY", True):
        raise RuntimeError("This build only supports FREE_ONLY=1")
    return {
        "free_only": True, "demo": env_bool("DEMO_MODE"), "skip_audio": env_bool("SKIP_AUDIO"),
        "currents_key": os.getenv("CURRENTS_API_KEY", "").strip(),
        "guardian_key": os.getenv("GUARDIAN_API_KEY", "").strip(),
        "nasa_key": os.getenv("NASA_API_KEY", "DEMO_KEY").strip() or "DEMO_KEY",
        "unsplash_key": os.getenv("UNSPLASH_ACCESS_KEY", "").strip(),
        "local_image_url": os.getenv("LOCAL_IMAGE_API_URL", "").strip(),
        "local_image_steps": max(8, env_int("LOCAL_IMAGE_STEPS", 20)),
        "local_image_timeout": max(30, env_int("LOCAL_IMAGE_TIMEOUT", 180)),
        "libre_url": os.getenv("LIBRETRANSLATE_URL", "http://127.0.0.1:5000").strip(),
        "libre_key": os.getenv("LIBRETRANSLATE_API_KEY", "").strip(),
        "ollama_url": os.getenv("OLLAMA_URL", "").strip(),
        "ollama_model": os.getenv("OLLAMA_MODEL", "llama3.2:3b").strip(),
        "retention_days": max(7, env_int("RETENTION_DAYS", 30)),
        "backfill_days": max(1, min(7, env_int("BACKFILL_DAYS", 1))),
        "tts_provider": os.getenv("READING_TTS_PROVIDER", "edge").strip().lower(),
        "timeout": max(5, env_int("REQUEST_TIMEOUT", 25)),
        "limits": {
            "currents": max(1, env_int("CURRENTS_DAILY_LIMIT", 2)),
            "guardian": max(1, env_int("GUARDIAN_DAILY_LIMIT", 2)),
            "nasa": max(1, env_int("NASA_DAILY_LIMIT", 2)),
            "nws": max(1, env_int("NWS_DAILY_LIMIT", 2)),
            "usgs": max(1, env_int("USGS_DAILY_LIMIT", 2)),
            "arxiv": max(1, env_int("ARXIV_DAILY_LIMIT", 2)),
            "unsplash": max(1, env_int("UNSPLASH_DAILY_LIMIT", 10)),
            "openverse": max(1, env_int("OPENVERSE_DAILY_LIMIT", 10)),
            "commons": max(1, env_int("COMMONS_DAILY_LIMIT", 10)),
        },
    }


def main() -> int:
    load_dotenv(ROOT / ".env")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    for path in (RAW_DIR, PROCESSED_DIR, CACHE_DIR, QUOTA_DIR, AUDIO_CACHE_DIR):
        path.mkdir(parents=True, exist_ok=True)
    config = config_from_env()
    cleanup(config["retention_days"])
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    quota = QuotaManager(config["limits"])
    today_date = utc_now().date()
    today = today_date.isoformat()
    retained_articles = load_articles(config["retention_days"])
    target_dates = [
        (today_date - timedelta(days=days_ago)).isoformat()
        for days_ago in range(config["backfill_days"])
    ]
    dates_to_build = []
    for target_date in target_dates:
        existing = [row for row in retained_articles if row["published_date"] == target_date]
        if (
            len(existing) != DAILY_ARTICLE_COUNT
            or (not config["demo"] and is_demo_edition(existing))
            or (target_date == today and env_bool("REFRESH_TODAY", False))
        ):
            dates_to_build.append(target_date)
    if dates_to_build:
        candidates = collect_candidates(session, quota, config)
        atomic_json(RAW_DIR / f"{today}-providers.json", {
            "fetched_at": utc_now().isoformat(), "candidates": candidates,
        })
        translator = Translator(session, config)
        for date_index, target_date in enumerate(dates_to_build):
            selected = choose_daily_articles(candidates, offset=date_index * DAILY_ARTICLE_COUNT)
            if len(selected) != DAILY_ARTICLE_COUNT:
                raise RuntimeError("Free providers did not supply enough valid articles; existing site was preserved")
            processed: list[dict[str, Any]] = []
            for index, raw in enumerate(selected, 1):
                logging.info("[%s %d/%d] Building %s: %s", target_date, index, DAILY_ARTICLE_COUNT, raw["level"], raw["title"])
                processed.append(process_article(raw, session, quota, translator, config, target_date))
            output_dir = PROCESSED_DIR / target_date
            temporary = PROCESSED_DIR / f".{target_date}-staging"
            if temporary.exists():
                shutil.rmtree(temporary)
            temporary.mkdir(parents=True)
            for article in processed:
                atomic_json(temporary / f"{article['slug']}.json", article)
            if output_dir.exists():
                shutil.rmtree(output_dir)
            temporary.replace(output_dir)
        if not config["demo"]:
            purge_demo_editions()
    articles = load_articles(config["retention_days"])
    render_site(articles, quota)
    logging.info("Published %d retained article(s).", len(articles))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        logging.error("%s", error)
        raise SystemExit(1)
