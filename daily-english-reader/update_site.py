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
import unicodedata
import warnings
import wave
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, unquote, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo

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
BUILD_REPORT_PATH = DATA_DIR / "build-report.json"
PROVIDER_STATUS_PATH = DATA_DIR / "provider-status.json"
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
SCHEMA_VERSION = 9
TRANSLATION_CACHE_VERSION = 2
IMAGE_CACHE_VERSION = 2
TORONTO_ZONE = ZoneInfo("America/Toronto")
MAX_SOURCE_AGE_HOURS = 48
LEVELS = ("A1", "A2", "B1", "B2", "C1")
TARGET_PER_LEVEL = 2
DAILY_ARTICLE_COUNT = len(LEVELS) * TARGET_PER_LEVEL
PRACTICE_SOURCE_NAME = "Learning Hub Practice Story"
PRACTICE_CONTENT_TYPE = "fictional_practice_story"
PRACTICE_DISCLAIMER_EN = "Fictional learning story created for English practice. This is not real news."
PRACTICE_DISCLAIMER_TH = "เรื่องอ่านฝึกภาษา แต่งขึ้นเพื่อการเรียนภาษาอังกฤษ ไม่ใช่ข่าวจริง"

PRACTICE_TOPICS = [
    ("The umbrella at the bus stop", "Daily Life", "Mina finds a blue umbrella at a quiet bus stop after the rain. She asks nearby shop owners about it and leaves a careful note. The next morning, an older man returns and is happy to find the umbrella his daughter gave him."),
    ("A garden above the bakery", "Environment", "A small bakery starts a garden on its flat roof. Staff grow herbs for bread and flowers for bees. Neighbors help carry soil upstairs, and the project gives the busy street a cooler and greener place."),
    ("The library's silent hour", "Education", "A community library creates one silent hour every afternoon for students who need a calm place to study. Visitors turn off phone sounds, volunteers prepare simple study guides, and many learners discover that they can focus better."),
    ("A bicycle with a second purpose", "Technology", "Ken repairs an old bicycle and connects it to a small generator. People at the community center pedal it to charge lights during evening classes. The invention is simple, but it helps everyone learn about energy."),
    ("The notebook from platform six", "Travel", "During a train journey, Lila discovers a notebook filled with sketches of towns along the route. She follows the owner's clues, meets helpful passengers, and returns it to a young artist at the final station."),
    ("Lunch for a new neighbor", "Community", "A family notices that their new neighbor eats alone each day. They invite him to share lunch in the courtyard. He brings a recipe from his hometown, and the meal becomes a weekly gathering for the building."),
    ("The night class telescope", "Science", "Students in an evening science class build a basic telescope from donated parts. Their first view of the moon is not perfectly clear, yet it inspires them to record observations and improve the design together."),
    ("A map made from memories", "Culture", "An art teacher asks local residents to draw places that matter to them. The drawings become a large neighborhood map showing old trees, favorite shops, and shared memories that ordinary street maps often miss."),
    ("The cafe that borrowed cups", "Environment", "A cafe tests a reusable cup program with nearby offices. Customers borrow a cup and return it later to any partner shop. At first the system is confusing, but clear signs and patient staff make it easier."),
    ("Messages for the morning team", "Work", "Two teams share the same workshop at different times. They begin leaving short voice messages about unfinished tasks and safety checks. The habit prevents mistakes and helps the morning and evening workers trust each other."),
    ("The seed exchange shelf", "Nature", "Residents place labeled packets of vegetable seeds on a shelf outside the town hall. Anyone may take one packet and later return seeds from a successful plant. The exchange slowly creates more variety in local gardens."),
    ("A small museum of ordinary things", "Culture", "A school opens a temporary museum containing everyday objects from different generations. Students interview relatives about radios, lunch boxes, tools, and letters, then write short explanations about how daily life has changed."),
]

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

TRANSLATION_SIMPLIFICATIONS = {
    "have been subject to": "had",
    "has been subject to": "had",
    "prompting": "causing",
    "next fiscal year": "next budget year",
    "sanitary napkins": "menstrual pads",
    "menstrual items": "menstrual products",
    "wipes out": "removes",
    "out of reach for": "too expensive for",
    "violating their human rights": "breaking laws that protect their human rights",
    "violating our human rights": "breaking laws that protect our human rights",
    "internal medicine resident": "doctor training in internal medicine",
    "metro area": "metropolitan area",
    "pea-sized hail": "small hailstones",
    "ping pong ball size hail": "hailstones the size of ping pong balls",
    "was located near": "was near",
    "nuclear inspections": "inspections of nuclear facilities",
    "free transit through the Strait of Hormuz": "free passage through the Hormuz Strait",
    "petrochemical and petroleum products": "petrochemical products and oil products",
    "algae": "green plant material in water",
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

NEWS_WORDS = {
    "a": "", "an": "", "as": "ขณะที่", "bbc": "บีบีซี", "camera": "กล้อง", "captured": "บันทึกภาพ",
    "close": "ใกล้", "concerned": "กังวล", "described": "เล่าว่า", "diver": "นักดำน้ำ",
    "endangered": "ใกล้สูญพันธุ์", "encounter": "การพบเจอ", "filmed": "ถ่ายวิดีโอ", "film": "ถ่ายทำ",
    "fingers": "นิ้วมือ", "footage": "ภาพวิดีโอ", "great": "ใหญ่", "incredibly": "อย่างมาก",
    "mediterranean": "ทะเลเมดิเตอร์เรเนียน", "moment": "ช่วงเวลานั้น", "operating": "ใช้งาน",
    "pretty": "ค่อนข้าง", "rare": "หายาก", "remmers": "เรมเมอร์ส", "scientists": "นักวิทยาศาสตร์",
    "sea": "ทะเล", "shaking": "มือสั่น", "shark": "ฉลาม", "sicily": "ซิซิลี", "special": "พิเศษ",
    "told": "บอก", "trembling": "สั่น", "tunisia": "ตูนิเซีย", "volunteer": "อาสาสมัคร", "white": "ขาว",
    "africa": "แอฟริกา", "age": "อายุ", "awards": "รางวัล", "coverage": "การรายงานข่าว",
    "football": "ฟุตบอล", "grannies": "คุณยาย", "journalism": "สื่อสารมวลชน", "soccer": "ฟุตบอล",
    "tournament": "การแข่งขัน", "world cup": "ฟุตบอลโลก",
}

NEWS_WORDS.update({
    "activists": "นักเคลื่อนไหว", "budget": "งบประมาณ", "contraceptives": "ยาคุมกำเนิด",
    "decades": "หลายสิบปี", "dropping": "ลดลง", "fiscal": "ปีงบประมาณ",
    "goods": "สินค้า", "huizeng": "ฮุ่ยเจิง", "impact": "ผลกระทบ", "items": "สินค้า",
    "luxury": "ฟุ่มเฟือย", "menstrual": "เกี่ยวกับประจำเดือน", "napkins": "ผ้าอนามัย",
    "npr": "เอ็นพีอาร์", "pakistan": "ปากีสถาน", "price": "ราคา", "prices": "ราคา",
    "products": "ผลิตภัณฑ์", "prompting": "ทำให้เกิด", "protests": "การประท้วง",
    "reach": "เอื้อมถึง", "rf": "อาร์เอฟ", "sales": "ยอดขาย/ภาษีขาย",
    "sanitary": "เกี่ยวกับสุขอนามัย", "subject": "อยู่ภายใต้", "taxed": "ถูกเก็บภาษี",
    "zero": "ศูนย์",
})

PHRASE_TRANSLATIONS = [
    (
        "rare footage captured of great white shark in mediterranean sea",
        "มีการบันทึกภาพฉลามขาวใหญ่ที่พบได้ยากในทะเลเมดิเตอร์เรเนียน",
    ),
    (
        "a volunteer diver has described shaking as he filmed his encounter with an endangered great white shark between tunisia and sicily",
        "นักดำน้ำอาสาคนหนึ่งเล่าว่าเขามือสั่นตอนถ่ายวิดีโอ ขณะพบฉลามขาวใหญ่ที่ใกล้สูญพันธุ์บริเวณระหว่างตูนิเซียกับซิซิลี",
    ),
    (
        "a diver filmed an incredibly rare encounter with a great white shark in the mediterranean sea",
        "นักดำน้ำคนหนึ่งถ่ายวิดีโอการพบฉลามขาวใหญ่ที่หาได้ยากมากในทะเลเมดิเตอร์เรเนียน",
    ),
    (
        "the shark was pretty close to us",
        "ฉลามว่ายเข้ามาใกล้พวกเขามาก",
    ),
    (
        "my fingers were trembling when i was trying to get the camera operating",
        "นิ้วของเขาสั่นขณะพยายามเปิดกล้องเพื่อถ่ายภาพ",
    ),
    (
        "scientists say people should not be concerned",
        "นักวิทยาศาสตร์บอกว่าผู้คนไม่จำเป็นต้องกังวล",
    ),
]

PHRASE_TRANSLATIONS.extend([
    (
        "pakistan ends luxury tax on menstrual products contraceptives will prices drop",
        "ปากีสถานยกเลิกภาษีสินค้าฟุ่มเฟือยสำหรับผลิตภัณฑ์ประจำเดือนและยาคุมกำเนิด คำถามคือราคาจะลดลงหรือไม่",
    ),
    (
        "in pakistan taxes on menstrual products can add up activists have long worked to change this now a new budget wipes out the 18% sales tax but questions remain about the impact on prices",
        "ในปากีสถาน ภาษีผลิตภัณฑ์ประจำเดือนทำให้ราคาสูงขึ้น นักเคลื่อนไหวพยายามผลักดันให้เปลี่ยนเรื่องนี้มานาน ตอนนี้งบประมาณใหม่ยกเลิกภาษีขาย 18% แล้ว แต่ยังมีคำถามว่าราคาสินค้าจะลดลงจริงแค่ไหน",
    ),
    (
        "menstrual products have been subject to an 18% sales tax in pakistan prompting protests",
        "ผลิตภัณฑ์ประจำเดือนในปากีสถานเคยถูกเก็บภาษีขาย 18% จนทำให้เกิดการประท้วง",
    ),
    (
        "the budget for next fiscal year has the sales tax on these products dropping from 18% to zero",
        "งบประมาณปีถัดไปลดภาษีขายของสินค้ากลุ่มนี้จาก 18% เหลือศูนย์",
    ),
    (
        "for decades sanitary napkins and other menstrual items have been taxed as luxury goods",
        "เป็นเวลาหลายสิบปี ผ้าอนามัยและสินค้าสำหรับประจำเดือนอื่น ๆ ถูกเก็บภาษีเหมือนสินค้าฟุ่มเฟือย",
    ),
    (
        "the price has put these products out of reach for many in pakistan",
        "ราคาที่สูงทำให้หลายคนในปากีสถานซื้อสินค้าเหล่านี้ได้ยาก",
    ),
])

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


def toronto_now() -> datetime:
    return utc_now().astimezone(TORONTO_ZONE)


def expected_edition_date() -> str:
    return toronto_now().date().isoformat()


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
    raw = unicodedata.normalize("NFC", str(value or ""))
    text = BeautifulSoup(raw, "html.parser").get_text(" ") if "<" in raw and ">" in raw else html.unescape(raw)
    return re.sub(r"\s+", " ", text).strip()


def normalize_paragraphs(value: str) -> str:
    raw = unicodedata.normalize("NFC", str(value or "")).replace("\r\n", "\n")
    paragraphs = [normalize(part) for part in re.split(r"\n\s*\n", raw)]
    return "\n\n".join(part for part in paragraphs if part)


def slugify(value: str, limit: int = 72) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:limit].rstrip("-") or "story"


def sentence_split(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", normalize(text)) if part.strip()]


def clean_story_text(text: str) -> str:
    text = normalize(text)
    text = "".join(character for character in text if unicodedata.category(character) != "Cf")
    text = re.sub(r"\(SOUNDBITE OF [^)]+\)", " ", text, flags=re.I)
    text = re.sub(
        r"\bCopyright\s*(?:©|\(c\))?\s*\d{4}\s+NPR\.\s*All rights reserved\.",
        " ", text, flags=re.I,
    )
    text = re.sub(
        r"\bVisit our website terms of use and permissions pages at\s+\S+\s+for further information\.",
        " ", text, flags=re.I,
    )
    text = re.sub(
        r"\*?\s*(WHAT|WHERE|WHEN|IMPACTS|ADDITIONAL DETAILS|HAZARD|SOURCE|IMPACT)\.{2,}\s*",
        lambda match: f" {match.group(1).title()}: ",
        text,
        flags=re.I,
    )
    text = re.sub(r"\bFor the following areas\.{2,}\s*", " ", text, flags=re.I)
    text = re.sub(r"\b(include|includes|including)\.{2,}\s*", r"\1 ", text, flags=re.I)
    text = re.sub(r"https?://\S+", " ", text, flags=re.I)
    text = re.sub(r"\s+-\s+", ". ", text)
    text = re.sub(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+){0,3}/(?:iStockphoto|Getty Images|AP|Reuters)[^.!?]*hide caption\b", " ", text)
    text = re.sub(r"\bhide caption\b", " ", text, flags=re.I)
    text = re.sub(r"\bUNIDENTIFIED(?:\s+[A-Z]+){0,4}\s*#\d+\s*[,.:]?\s*", " ", text, flags=re.I)
    text = re.sub(r"\b(?:SCOTT DETROW|A MARTÍNEZ|HOST|BYLINE|EDITOR'S NOTE):\s*", " ", text, flags=re.I)
    text = re.sub(r"\b(?:Image source|Getty Images|Reuters|Associated Press|AP Photo)\b[^.!?]*(?:\.|$)", " ", text, flags=re.I)
    text = re.sub(r"\b2e\b", "we", text)
    text = re.sub(r"\byou['’]ve never too old\b", "you're never too old", text, flags=re.I)
    text = re.sub(r"\band\.\s+(Other\b)", lambda match: f"and {match.group(1).lower()}", text, flags=re.I)
    text = re.sub(r"\band\.\s+(?=The\b)", ". ", text, flags=re.I)
    text = re.sub(r"\band\.\s+([A-Z][a-z]+)", lambda match: f"and {match.group(1).lower()}", text)
    text = re.sub(
        r"\b(of|to|for|with|from|in|over|by)\.\s+([A-Z][a-z]+)",
        lambda match: f"{match.group(1)} {match.group(2).lower()}",
        text,
    )
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\b([A-Z])\s*\.\s+([A-Z][a-z])", r"\1. \2", text)
    text = re.sub(r"(?<!\b[A-Z])\.\s+(?=[a-z])", ", ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def clean_english_fragments(text: str) -> str:
    text = clean_story_text(text)
    month_names = {
        "Jan": "January", "Feb": "February", "Mar": "March", "Apr": "April",
        "Jun": "June", "Jul": "July", "Aug": "August", "Sep": "September",
        "Sept": "September", "Oct": "October", "Nov": "November", "Dec": "December",
    }
    text = re.sub(
        r"\b(Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.\s+(?=\d{1,2}\b)",
        lambda match: month_names[match.group(1)] + " ", text,
    )
    text = re.sub(
        r"\b(Depending on|According to|Based on|Because of|Part of)\.\s+(?=[a-z])",
        r"\1 ", text, flags=re.I,
    )
    text = re.sub(r"\bpea size hail\b", "pea-sized hail", text, flags=re.I)
    text = re.sub(r"\bping pong ball size hail\b", "hailstones the size of ping pong balls", text, flags=re.I)
    text = re.sub(r"\b(What|Where|When|Impacts?|Additional Details|Hazard|Source)\.\s+(?=[A-Z0-9])", r"\1: ", text)
    text = re.sub(r"\b(Of|To|For|With|From|In|By),\s+(but|and)\b", r"\1 \2", text)
    text = re.sub(r"\b(It|They|He|She),\s+(?=[a-z])", r"\1 ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def normalize_weather_for_speech(text: str) -> str:
    def clock(match: re.Match[str]) -> str:
        digits, period, zone = match.groups()
        digits = digits.zfill(4)
        hour = str(int(digits[:-2]))
        minute = digits[-2:]
        zones = {
            "EDT": "Eastern Daylight Time", "EST": "Eastern Standard Time",
            "CDT": "Central Daylight Time", "CST": "Central Standard Time",
            "MDT": "Mountain Daylight Time", "MST": "Mountain Standard Time",
            "PDT": "Pacific Daylight Time", "PST": "Pacific Standard Time",
        }
        zone_key = (zone or "").upper()
        zone_text = zones.get(zone_key, zone_key)
        clock_text = hour if minute == "00" else f"{hour}:{minute}"
        return f"{clock_text} {period.upper()}{f' {zone_text}' if zone_text else ''}"

    text = re.sub(r"\b(\d{3,4})\s*(AM|PM)(?:\s*(EDT|EST|CDT|CST|MDT|MST|PDT|PST))?\b", clock, text, flags=re.I)
    text = re.sub(r"\b(\d+(?:\.\d+)?)\s*mph\b", r"\1 miles per hour", text, flags=re.I)
    return text


def paragraphize_text(text: str, sentences_per_paragraph: int = 3) -> str:
    sentences = sentence_split(clean_english_fragments(text))
    if not sentences:
        return ""
    deduplicated: list[str] = []
    for sentence in sentences:
        if not deduplicated or phrase_key(sentence) != phrase_key(deduplicated[-1]):
            deduplicated.append(sentence)
    sentences = deduplicated
    groups = [sentences[index:index + sentences_per_paragraph] for index in range(0, len(sentences), sentences_per_paragraph)]
    return "\n\n".join(" ".join(group) for group in groups)


def prepare_reader_text(text: str) -> str:
    return paragraphize_text(normalize_weather_for_speech(clean_english_fragments(text)))


def make_speech_text(title: str, text: str) -> str:
    title = clean_english_fragments(title)
    if title and title[-1] not in ".!?":
        title += "."
    body = prepare_reader_text(text)
    return "\n\n".join(part for part in (title, body) if part)


def speech_text_issues(text: str) -> list[str]:
    issues: list[str] = []
    if not normalize(text):
        return ["empty-speech-text"]
    if re.search(r"https?://|\bhide caption\b|\bimage credit\b", text, re.I):
        issues.append("speech-metadata-leakage")
    if re.search(r"\b(?:Depending on|According to|Based on|Because of|Part of)\.\s+[a-z]", text, re.I):
        issues.append("broken-preposition-fragment")
    if re.search(r"\b(?:Of|To|For|With|From|In|By),\s+(?:but|and)\b|\b(?:It|They|He|She),\s+[a-z]", text):
        issues.append("broken-comma-fragment")
    if re.search(r"\b(?:WHAT|WHERE|WHEN|IMPACTS?|HAZARD|SOURCE)\.{2,}", text, re.I):
        issues.append("weather-machine-fragment")
    return issues


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


_PODCAST_GLOSSARY: dict[str, str] | None = None


def podcast_glossary() -> dict[str, str]:
    global _PODCAST_GLOSSARY
    if _PODCAST_GLOSSARY is not None:
        return _PODCAST_GLOSSARY
    glossary: dict[str, str] = {}
    for path in [
        STATIC_DIR / "data" / "podcast-flashcards.json",
        ROOT.parent / "deploy-rollback-original" / "oxford-translations.json",
    ]:
        payload = load_json(path, {})
        if isinstance(payload.get("cards"), list):
            for card in payload["cards"]:
                word = normalize(str(card.get("word", ""))).lower()
                meaning = normalize(str(card.get("meaning", "")))
                if word and meaning and "ยังไม่มี" not in meaning:
                    glossary.setdefault(word, meaning)
        if isinstance(payload.get("entries"), dict):
            for word, row in payload["entries"].items():
                meaning = normalize(str(row.get("meaning", ""))) if isinstance(row, dict) else ""
                if word and meaning:
                    glossary.setdefault(str(word).lower(), meaning)
    _PODCAST_GLOSSARY = glossary
    return glossary


def thai_gloss(word: str) -> str:
    key = word.lower().strip("'")
    glossary = podcast_glossary()
    if key in NEWS_WORDS:
        return NEWS_WORDS[key]
    if key in THAI_WORDS:
        return THAI_WORDS[key]
    if key in glossary:
        return glossary[key]
    irregular = {
        "filming": "ถ่ายวิดีโอ", "films": "ถ่ายวิดีโอ", "divers": "นักดำน้ำ",
        "sharks": "ฉลาม", "scientist": "นักวิทยาศาสตร์", "capturing": "บันทึกภาพ",
    }
    if key in irregular:
        return irregular[key]
    stem = re.sub(r"(ing|ed|es|s)$", "", key)
    if stem in NEWS_WORDS:
        return NEWS_WORDS[stem]
    if stem in THAI_WORDS:
        return THAI_WORDS[stem]
    if stem in glossary:
        return glossary[stem]
    if key.endswith("ly"):
        base = thai_gloss(key[:-2])
        return f"อย่าง{base}" if base and not base.startswith("คำว่า") else ""
    if key.endswith(("tion", "sion", "ment", "ness", "ity")):
        return ""
    return ""


def looks_mojibake(value: str) -> bool:
    return bool(re.search(r"[\u0080-\u009f\ufffd]|โ€|Ã.|Â.", str(value or "")))


def safe_word_translations(words: list[str], translated: dict[str, str] | None = None) -> dict[str, str]:
    output: dict[str, str] = {}
    for word in words:
        value = normalize((translated or {}).get(word, ""))
        if not value or value.lower() == word.lower() or looks_mojibake(value):
            value = thai_gloss(word)
        output[word] = value
    return output


def phrase_key(text: str) -> str:
    return re.sub(r"[^a-z0-9%]+", " ", normalize(text).lower()).strip()


def translated_phrase(text: str) -> str:
    key = phrase_key(text)
    for phrase, thai in PHRASE_TRANSLATIONS:
        if phrase_key(phrase) in key:
            return thai
    return ""


def exact_translated_phrase(text: str) -> str:
    key = phrase_key(text)
    for phrase, thai in PHRASE_TRANSLATIONS:
        if phrase_key(phrase) == key:
            return thai
    return ""


def simplify_translation_source(text: str) -> str:
    output = text
    for original, replacement in TRANSLATION_SIMPLIFICATIONS.items():
        output = re.sub(rf"\b{re.escape(original)}\b", replacement, output, flags=re.I)
    output = re.sub(
        r"\b(\d+(?:\.\d+)?)-year prison sentence\b",
        r"prison sentence of \1 years",
        output,
        flags=re.I,
    )
    return normalize_written_measurements(output)


def sentence_to_thai(sentence: str) -> str:
    direct = translated_phrase(sentence)
    if direct:
        return direct
    return ""


def article_thai_sentences(raw: dict[str, Any], text: str) -> list[str]:
    candidates = [raw.get("title", ""), raw.get("description", ""), *sentence_split(text)[:6]]
    output: list[str] = []
    seen: set[str] = set()
    for sentence in candidates:
        thai = sentence_to_thai(sentence)
        if thai and thai not in seen:
            output.append(thai)
            seen.add(thai)
        if len(output) >= 6:
            break
    return output


THAI_MONTHS = {
    "January": "มกราคม", "February": "กุมภาพันธ์", "March": "มีนาคม", "April": "เมษายน",
    "May": "พฤษภาคม", "June": "มิถุนายน", "July": "กรกฎาคม", "August": "สิงหาคม",
    "September": "กันยายน", "October": "ตุลาคม", "November": "พฤศจิกายน", "December": "ธันวาคม",
}
THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
WRITTEN_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}


def normalize_written_measurements(text: str) -> str:
    units = r"miles?|knots?|degrees?|percent|per cent|dollars?"
    words = "|".join(WRITTEN_NUMBERS)
    return re.sub(
        rf"\b({words})\b(?=\s+(?:{units})\b)",
        lambda match: str(WRITTEN_NUMBERS[match.group(1).lower()]), text, flags=re.I,
    )


def repair_translated_facts(source: str, translated: str) -> str:
    source = normalize_written_measurements(source)
    for value, rate in re.findall(r"\b(\d+(?:\.\d+)?)\s+miles?(\s+per\s+hour)?\b", source, re.I):
        replacement = "ไมล์ต่อชั่วโมง" if rate else "ไมล์"
        translated = re.sub(
            rf"\b({re.escape(value)}\s*)(?:กิโลเมตร|มิล|เมล|ไมล|kilometers?|kilometres?|km)(?:\s*ต่อ\s*ชั่วโมง)?\b",
            rf"\1{replacement}", translated, flags=re.I,
        )
    target_numbers = numeric_facts(translated)
    for month, thai_month in THAI_MONTHS.items():
        for day in re.findall(rf"\b{month}\s+(\d{{1,2}})\b", source):
            if day not in target_numbers and thai_month in translated:
                translated = translated.replace(thai_month, f"{thai_month} {day}", 1)
    source_months = {
        month for month in THAI_MONTHS
        if re.search(rf"(?:\b(?:in|on|since|until|through|during|by|from)\s+{month}\b|\b{month}\s+\d{{1,2}}\b)", source, re.I)
    }
    if len(source_months) == 1:
        expected_month = THAI_MONTHS[next(iter(source_months))]
        present_months = [thai_month for thai_month in THAI_MONTHS.values() if thai_month in translated]
        if expected_month not in translated and len(present_months) == 1:
            translated = translated.replace(present_months[0], expected_month, 1)
    for clock, period in re.findall(r"\b(\d{1,2}:\d{2})\s*(AM|PM)\b", source, re.I):
        hour, minute = clock.split(":", 1)
        target_clock = rf"(?<!\d){re.escape(str(int(hour)))}[.:]{re.escape(minute)}(?!\d)"
        match = re.search(target_clock, translated)
        if not match:
            continue
        suffix = translated[match.end():match.end() + 18]
        if not re.match(r"\s*(?:AM|PM)\b", suffix, re.I):
            translated = translated[:match.end()] + f" {period.upper()}" + translated[match.end():]
    target_numbers = numeric_facts(translated)
    missing_knots = [
        value for value in re.findall(r"\b(\d+(?:\.\d+)?)\s+knots?\b", source, re.I)
        if value not in target_numbers
    ]
    if missing_knots:
        translated = normalize_paragraphs(
            f"{translated}\n\nค่าความเร็วที่ระบุเพิ่มเติมคือ {', '.join(missing_knots)} นอต."
        )
        target_numbers = numeric_facts(translated)
    for years in re.findall(r"\b(\d+(?:\.\d+)?)-year prison sentence\b", source, re.I):
        if years not in target_numbers:
            translated = normalize_paragraphs(f"{translated}\n\nโทษจำคุกที่ระบุไว้คือ {years} ปี.")
    return translated


def numeric_facts(text: str) -> set[str]:
    text = text.translate(THAI_DIGITS)
    facts = {match.replace(".", ":") for match in re.findall(r"(?<!\w)\d{1,2}[.:]\d{2}(?!\d)", text)}
    text = re.sub(r"(?<!\w)\d{1,2}[.:]\d{2}(?!\d)", " ", text)
    facts.update(match.replace(",", "") for match in re.findall(r"(?<!\w)\d[\d,]*(?:\.\d+)?", text))
    return facts


def repeated_translation_issues(text: str) -> list[str]:
    tokens = re.findall(r"[\u0e00-\u0e7f]+|[A-Za-z]+|\d+(?:[.,:]\d+)*", text.lower())
    issues: list[str] = []
    run = 1
    for index in range(1, len(tokens)):
        run = run + 1 if tokens[index] == tokens[index - 1] else 1
        if run >= 4:
            issues.append("repeated-word-run")
            break
    for size in (2, 3):
        counts = Counter(tuple(tokens[index:index + size]) for index in range(max(0, len(tokens) - size + 1)))
        if counts:
            count = max(counts.values())
            if count >= 4 and count * size >= max(8, len(tokens) // 3):
                issues.append(f"repeated-{size}-gram")
    if re.search(r"([\u0e00-\u0e7f]{2,12})(?:\1){3,}", text):
        issues.append("repeated-junk-string")
    return issues


def translation_quality_issues(source: str, translated: str) -> list[str]:
    raw_translated = str(translated or "").replace("\r\n", "\n")
    source = normalize_written_measurements(normalize_paragraphs(source))
    translated = normalize_paragraphs(translated)
    issues: list[str] = []
    if not translated:
        return ["empty-translation"]
    if re.search(r"\n\s*\n\s*\n", raw_translated):
        issues.append("empty-paragraph")
    if looks_mojibake(translated):
        issues.append("mojibake")
    if not re.search(r"[\u0e00-\u0e7f]", translated):
        issues.append("missing-thai-script")
    if re.search(r"[\u0e80-\u0eff\u1000-\u109f\u1780-\u17ff\u0400-\u04ff\u0600-\u06ff\u4e00-\u9fff]", translated):
        issues.append("unexpected-non-thai-script")
    placeholders = (
        "คำแปลภาษาไทยสำหรับบทความตัวอย่าง", "เนื้อหาข่าวพูดถึงเหตุการณ์สำคัญ",
        "ควรอ่านจากย่อหน้าภาษาอังกฤษ", "translation unavailable",
    )
    if any(value.lower() in translated.lower() for value in placeholders):
        issues.append("placeholder-text")
    issues.extend(repeated_translation_issues(translated))

    source_words = len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", source))
    thai_characters = len(re.findall(r"[\u0e00-\u0e7f]", translated))
    if thai_characters < max(12, int(source_words * 1.5)):
        issues.append("suspiciously-short")
    if source_words and thai_characters > source_words * 10 + 120:
        issues.append("suspiciously-long")
    missing_numbers = numeric_facts(source) - numeric_facts(translated)
    if missing_numbers:
        issues.append("missing-number:" + ",".join(sorted(missing_numbers)))
    for month, thai_month in THAI_MONTHS.items():
        month_context = rf"(?:\b(?:in|on|since|until|through|during|by|from)\s+{month}\b|\b{month}\s+\d{{1,2}}\b|\b\d{{1,2}}\s+{month}\b)"
        if re.search(month_context, source) and not re.search(rf"\b{month}\b", translated, re.I) and thai_month not in translated:
            issues.append("missing-month:" + month)
    if re.search(r"\b\d{1,2}:\d{2}\s*(?:AM|PM)\b", source, re.I):
        has_clock = bool(re.search(r"\b\d{1,2}[.:]\d{2}\b", translated))
        has_period = bool(re.search(r"\b(?:AM|PM)\b|น\.|ตอน(?:เช้า|บ่าย|ค่ำ)", translated, re.I))
        if not has_clock or not has_period:
            issues.append("missing-time-period")
    if re.search(r"%|\bper\s*cent\b|\bpercent\b", source, re.I) and not re.search(r"%|\bpercent\b|เปอร์เซ็นต์|ร้อยละ", translated, re.I):
        issues.append("missing-percent-unit")
    unit_pairs = {
        r"\bmiles?\b": ("mile", "miles", "ไมล์"),
        r"\bknots?\b": ("knot", "knots", "น็อต", "นอต"),
        r"\bdegrees?\b|°[CF]\b": ("degree", "degrees", "องศา", "°"),
        r"\bdollars?\b|[$]": ("dollar", "dollars", "$", "ดอลลาร์"),
    }
    lower_target = translated.lower()
    for pattern, equivalents in unit_pairs.items():
        if re.search(pattern, source, re.I) and not any(value.lower() in lower_target for value in equivalents):
            issues.append("missing-unit:" + pattern)

    source_sentences = sentence_split(source)
    target_sentences = [part for part in re.split(r"[.!?ฯ]+", translated) if normalize(part)]
    if len(source_sentences) >= 4 and len(target_sentences) < max(2, (len(source_sentences) + 1) // 2):
        issues.append("obvious-truncation")
    source_paragraphs = [part for part in source.split("\n\n") if part.strip()]
    target_paragraphs = [part for part in translated.split("\n\n") if part.strip()]
    if len(source_paragraphs) > 1 and len(target_paragraphs) < len(source_paragraphs):
        issues.append("collapsed-paragraphs")
    latin_words = re.findall(r"\b[A-Za-z]{2,}\b", translated)
    if len(latin_words) > max(10, source_words // 4):
        issues.append("excessive-english-leakage")
    return list(dict.fromkeys(issues))


def is_useful_thai_translation(source: str, translated: str) -> bool:
    return not translation_quality_issues(source, translated)


def natural_thai_article(raw: dict[str, Any], text: str) -> str:
    category = english_label_for_category(raw.get("category", "news"))
    provider = raw.get("provider", "แหล่งข่าว")
    level = raw.get("level", "")
    detail_sentences = article_thai_sentences(raw, text)
    details = " ".join(detail_sentences)
    if not details:
        details = "เนื้อหาข่าวพูดถึงเหตุการณ์สำคัญและผลกระทบที่ผู้อ่านควรติดตามต่อ โดยควรอ่านจากย่อหน้าภาษาอังกฤษด้านบนประกอบด้วย"
    return (
        f"ข่าวนี้มาจาก {provider} อยู่ในหมวด{category} และถูกเรียบเรียงเป็นระดับ {level}. "
        f"เนื้อหาข่าวคือ {details}"
    )


def full_thai_article(raw: dict[str, Any], text: str, translated: str) -> str:
    translated = naturalize_thai(translated)
    if raw.get("isFallback"):
        return f"{PRACTICE_DISCLAIMER_TH}\n\n{translated}"
    if not is_useful_thai_translation(text, translated):
        return natural_thai_article(raw, text)
    category = english_label_for_category(raw.get("category", "news"))
    provider = raw.get("provider", "แหล่งข่าว")
    level = raw.get("level", "")
    if translated[-1] not in ".!?。！？":
        translated += "."
    return (
        f"ข่าวนี้มาจาก {provider} อยู่ในหมวด{category} และถูกเรียบเรียงเป็นระดับ {level}. "
        f"เนื้อหาข่าวคือ\n\n{translated}"
    )


def article_translation_body(row: dict[str, Any]) -> str:
    translated = row.get("thai_text", "")
    if row.get("isFallback") and translated.startswith(PRACTICE_DISCLAIMER_TH):
        return translated[len(PRACTICE_DISCLAIMER_TH):].lstrip()
    return translated


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
        self.day = expected_edition_date()
        self.path = QUOTA_DIR / f"{self.day}.json"
        self.limits = limits
        self.state = load_json(self.path, {"date": self.day, "providers": {}})

    def record(self, provider: str) -> dict[str, Any]:
        row = self.state["providers"].setdefault(provider, {})
        defaults = {
            "enabled": True, "attempted": False, "selected_count": 0, "skipped_count": 0,
            "request_count": 0, "success_count": 0, "error_count": 0,
            "requests": 0, "errors": 0, "disabled": False, "disabled_reason": "",
            "cooldown_until": "", "last_success": "", "last_error": "", "skip_reasons": {},
        }
        for key, value in defaults.items():
            row.setdefault(key, value)
        return row

    def available(self, provider: str) -> bool:
        record = self.record(provider)
        limit = self.limits.get(provider, 30 if provider.startswith("rss_") else 1)
        if record["disabled"] or record["requests"] >= limit:
            return False
        cooldown = parse_date(record["cooldown_until"]) if record["cooldown_until"] else None
        return not cooldown or cooldown <= utc_now()

    def requested(self, provider: str) -> None:
        record = self.record(provider)
        record["attempted"] = True
        record["requests"] += 1
        record["request_count"] += 1
        self.save()

    def succeeded(self, provider: str) -> None:
        record = self.record(provider)
        record["success_count"] += 1
        record["last_success"] = utc_now().isoformat()
        self.save()

    def selected(self, provider: str, count: int = 1) -> None:
        self.record(provider)["selected_count"] += count
        self.save()

    def skipped(self, provider: str, reason: str, count: int = 1) -> None:
        record = self.record(provider)
        record["skipped_count"] += count
        record["skip_reasons"][reason] = record["skip_reasons"].get(reason, 0) + count
        self.save()

    def disable(self, provider: str, reason: str) -> None:
        record = self.record(provider)
        record["enabled"] = False
        record["disabled"] = True
        record["disabled_reason"] = reason
        self.save()

    def failed(self, provider: str, kind: str, message: str) -> None:
        record = self.record(provider)
        record["errors"] += 1
        record["error_count"] += 1
        record["last_error"] = f"{kind}: {message}"[:300]
        if kind in {"auth", "forbidden"}:
            record["disabled"] = True
            record["enabled"] = False
            record["disabled_reason"] = kind
        elif kind == "rate_limit":
            record["cooldown_until"] = (utc_now() + timedelta(days=1)).replace(
                hour=0, minute=5, second=0, microsecond=0
            ).isoformat()
        elif kind in {"server", "timeout"}:
            record["cooldown_until"] = (utc_now() + timedelta(minutes=30)).isoformat()
        self.save()

    def save(self) -> None:
        atomic_json(self.path, self.state)

    def public_status(
        self, *, demo_fallback_blocked: bool = True, expected_date: str | None = None,
    ) -> dict[str, Any]:
        return {
            "updated_at": utc_now().isoformat(),
            "build_date_utc": utc_now().date().isoformat(),
            "expected_toronto_date": expected_date or expected_edition_date(),
            "demo_fallback_blocked": demo_fallback_blocked,
            "providers": {
                name: {
                    "provider": name,
                    "enabled": row["enabled"] and not row["disabled"],
                    "attempted": row["attempted"],
                    "selected_count": row["selected_count"],
                    "skipped_count": row["skipped_count"],
                    "request_count": row["request_count"],
                    "success_count": row["success_count"],
                    "error_count": row["error_count"],
                    "soft_limit": self.limits.get(name, 30 if name.startswith("rss_") else 0),
                    "available": self.available(name),
                    "last_success": row["last_success"],
                    "cooldown_until": row["cooldown_until"],
                    "last_error": row["last_error"],
                    "disabled_reason": row["disabled_reason"],
                    "skip_reasons": row["skip_reasons"],
                }
                for name in sorted(self.state["providers"])
                for row in [self.record(name)]
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
            payload = response.json()
            quota.succeeded(provider)
            return payload
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
    image_url: str = "", thai_demo: str = "", provider_key: str = "",
) -> dict[str, Any] | None:
    title, description = normalize(title), normalize(description)
    if not title or len(description.split()) < 18 or not url:
        return None
    return {
        "id": stable_id(provider, url, title), "provider": provider, "title": title,
        "description": description, "url": url, "category": category.title(),
        "published": parse_date(published).isoformat(), "author": normalize(author),
        "content_type": content_type, "image_url": image_url, "thai_demo": thai_demo,
        "provider_key": provider_key or slugify(provider, 32),
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


def practice_story_candidates(level: str, published_date: str) -> list[dict[str, Any]]:
    if level not in LEVELS:
        raise ValueError(f"Unsupported CEFR level: {level}")
    start = LEVELS.index(level) * TARGET_PER_LEVEL
    rows = []
    for attempt in range(4):
        title, category, description = PRACTICE_TOPICS[(start + attempt) % len(PRACTICE_TOPICS)]
        identifier = f"practice-{published_date}-{level.lower()}-{attempt + 1}"
        rows.append({
            "id": stable_id("practice", identifier, title),
            "provider": PRACTICE_SOURCE_NAME,
            "provider_key": "practice_story",
            "title": title,
            "description": description,
            "url": "",
            "category": category,
            "published": f"{published_date}T12:00:00+00:00",
            "author": "Learning Hub",
            "content_type": "fictional practice story",
            "image_url": "",
            "thai_demo": "",
            "level": level,
            "isFallback": True,
            "isRealNews": False,
            "contentType": PRACTICE_CONTENT_TYPE,
            "sourceName": PRACTICE_SOURCE_NAME,
            "disclaimerEn": PRACTICE_DISCLAIMER_EN,
            "disclaimerTh": PRACTICE_DISCLAIMER_TH,
        })
    return rows


def fallback_metadata_issues(row: dict[str, Any]) -> list[str]:
    expected = {
        "isFallback": True,
        "isRealNews": False,
        "contentType": PRACTICE_CONTENT_TYPE,
        "sourceName": PRACTICE_SOURCE_NAME,
        "disclaimerEn": PRACTICE_DISCLAIMER_EN,
        "disclaimerTh": PRACTICE_DISCLAIMER_TH,
    }
    return [f"invalid-{key}" for key, value in expected.items() if row.get(key) != value]


def fetch_currents(session: requests.Session, quota: QuotaManager, config: dict[str, Any]) -> list[dict[str, Any]]:
    key = config["currents_key"]
    if not key:
        quota.disable("currents", "missing optional free API key")
        return []
    payload = request_json(session, quota, "currents", CURRENTS_URL, params={
        "language": "en", "page_size": 30, "apiKey": key,
    }, timeout=config["timeout"])
    return [item for row in payload.get("news", []) if (item := normalized_article(
        "Currents", row.get("title", ""), row.get("description", ""), row.get("url", ""),
        (row.get("category") or ["World"])[0] if isinstance(row.get("category"), list) else row.get("category", "World"),
        row.get("published"), author=row.get("author", ""), provider_key="currents",
    ))]


def fetch_guardian(session: requests.Session, quota: QuotaManager, config: dict[str, Any]) -> list[dict[str, Any]]:
    key = config["guardian_key"]
    if not key:
        quota.disable("guardian", "missing optional free API key")
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
            content_type="news", image_url=fields.get("thumbnail", ""), provider_key="guardian",
        )
        if item:
            articles.append(item)
    return articles


def fetch_rss(session: requests.Session, quota: QuotaManager, config: dict[str, Any]) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    for provider, category, url in RSS_FEEDS:
        quota_name = f"rss_{slugify(provider + '-' + category, 24)}"
        if not quota.available(quota_name):
            quota.skipped(quota_name, "quota or cooldown")
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
                provider_key=quota_name,
            )
            if item:
                articles.append(item)
        quota.succeeded(quota_name)
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
    payload = request_json(session, quota, "nws", NWS_ALERTS_URL, params={"status": "actual"},
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
        quota.succeeded("arxiv")
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
        provider_key = article.get("provider_key", slugify(article["provider"], 32))
        if parse_date(article["published"]) < utc_now() - timedelta(hours=MAX_SOURCE_AGE_HOURS):
            quota.skipped(provider_key, "source older than 48 hours")
            continue
        if article["id"] in unique:
            quota.skipped(provider_key, "duplicate article")
            continue
        unique[article["id"]] = article
    return list(unique.values())


def complexity(text: str) -> float:
    sentences = sentence_split(text) or [text]
    words = re.findall(r"[A-Za-z]+", text)
    long_words = sum(len(word) >= 8 for word in words)
    return len(words) / max(1, len(sentences)) + long_words / max(1, len(words)) * 20


def ordered_daily_candidate_pool(candidates: list[dict[str, Any]], offset: int = 0) -> list[dict[str, Any]]:
    candidates = sorted(candidates, key=lambda row: complexity(row["description"]))
    if offset and candidates:
        shift = offset % len(candidates)
        candidates = candidates[shift:] + candidates[:shift]
    return candidates


def choose_daily_articles(candidates: list[dict[str, Any]], offset: int = 0) -> list[dict[str, Any]]:
    candidates = ordered_daily_candidate_pool(candidates, offset)
    if len(candidates) < DAILY_ARTICLE_COUNT:
        chosen = []
        for index, article in enumerate(candidates):
            row = dict(article)
            row["level"] = LEVELS[index % len(LEVELS)]
            chosen.append(row)
        return chosen
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


def replacement_daily_article(
    candidates: list[dict[str, Any]], level: str, used_ids: set[str], offset: int = 0,
) -> dict[str, Any] | None:
    for article in ordered_daily_candidate_pool(candidates, offset):
        if article["id"] in used_ids:
            continue
        row = dict(article)
        row["level"] = level
        return row
    return None


def record_candidate_failure(
    build_report: dict[str, Any], raw: dict[str, Any], level: str, error: Exception,
) -> None:
    reason = f"{type(error).__name__}: {error}"[:240]
    build_report.setdefault("candidate_rejections", []).append({
        "article_id": raw.get("id", ""),
        "title": raw.get("title", ""),
        "provider": raw.get("provider", ""),
        "level": level,
        "reason": reason,
    })


def build_level_readings(
    level: str, initial: list[dict[str, Any]], candidates: list[dict[str, Any]],
    used_ids: set[str], session: requests.Session, quota: QuotaManager,
    translator: Translator, config: dict[str, Any], published_date: str,
    build_report: dict[str, Any], offset: int = 0,
) -> list[dict[str, Any]]:
    processed: list[dict[str, Any]] = []
    queue = list(initial)
    practice = practice_story_candidates(level, published_date)
    while len(processed) < TARGET_PER_LEVEL:
        if queue:
            raw = queue.pop(0)
        else:
            raw = replacement_daily_article(candidates, level, used_ids, offset)
            if raw is None:
                raw = next((row for row in practice if row["id"] not in used_ids), None)
            if raw is None:
                raise RuntimeError(
                    f"Unable to produce {TARGET_PER_LEVEL} valid {level} readings after real-news and practice fallbacks"
                )
        used_ids.add(raw["id"])
        provider_key = raw.get("provider_key", slugify(raw["provider"], 32))
        quota.selected(provider_key)
        try:
            article = process_article(raw, session, quota, translator, config, published_date)
            validate_processed_article(article, level)
        except Exception as error:
            quota.skipped(provider_key, f"candidate rejected: {type(error).__name__}: {error}"[:240])
            record_candidate_failure(build_report, raw, level, error)
            logging.warning("Rejecting %s candidate %s: %s", level, raw.get("id", "unknown"), error)
            continue
        if article.get("isFallback"):
            build_report["practice_fallback_count"] = build_report.get("practice_fallback_count", 0) + 1
        processed.append(article)
    return processed


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
        sentence = re.sub(
            r",?\s+(although|however|while)\s+",
            lambda match: f". {match.group(1).capitalize()} ", sentence, flags=re.I,
        )
    output = []
    for piece in sentence_split(sentence) or [sentence]:
        words = piece.split()
        while words:
            if len(words) <= max_words + 4:
                chunk, words = words, []
            else:
                lower_bound = max(5, max_words - 4)
                upper_bound = min(len(words) - 1, max_words * 2)
                connector_breaks = [
                    index for index in range(lower_bound, upper_bound + 1)
                    if words[index].lower().strip(",") in {"and", "but", "so", "because", "while"}
                ]
                safe_breaks = connector_breaks
                if not safe_breaks:
                    # A longer complete sentence is safer than manufacturing
                    # fragments such as "through some. Of" for the translator.
                    chunk, words = words, []
                else:
                    breakpoint = min(safe_breaks, key=lambda index: abs(index - max_words))
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
                return clean_english_fragments(generated)
        except requests.RequestException:
            logging.warning("Ollama unavailable; using deterministic level adapter")
    sentences = sentence_split(clean_story_text(summary))
    _, max_words = sentence_budget(level)
    if level == "A1":
        parts = [part for sentence in sentences[:5] for part in simplify_sentence(sentence, 8, True)]
        return clean_english_fragments(trim_to_word_budget(parts[:10], max_words))
    if level == "A2":
        parts = [part for sentence in sentences[:6] for part in simplify_sentence(sentence, 12, True)]
        return clean_english_fragments(trim_to_word_budget(parts[:12], max_words))
    if level == "B1":
        parts = [part for sentence in sentences[:8] for part in simplify_sentence(sentence, 18, False)]
        return clean_english_fragments(trim_to_word_budget(parts[:12], max_words))
    if level == "B2":
        return clean_english_fragments(trim_to_word_budget(sentences[:9], max_words))
    return clean_english_fragments(trim_to_word_budget(sentences[:11], max_words))


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
        self._nllb_tokenizer: Any = None
        self._nllb_model: Any = None
        self.quality_diagnostics: dict[str, Any] = {
            "cache_rejections": 0, "nllb_retries": 0, "quality_failures": 0, "reasons": Counter(),
        }

    def _record_quality(self, field: str, issues: list[str]) -> None:
        self.quality_diagnostics[field] += 1
        self.quality_diagnostics["reasons"].update(issues)

    def diagnostics_summary(self) -> dict[str, Any]:
        return {
            "cache_rejections": self.quality_diagnostics["cache_rejections"],
            "nllb_retries": self.quality_diagnostics["nllb_retries"],
            "quality_failures": self.quality_diagnostics["quality_failures"],
            "rejection_reasons": dict(self.quality_diagnostics["reasons"]),
        }

    def _nllb_with_quality_retry(self, text: str) -> str:
        translated = self._nllb_translate(text)
        issues = translation_quality_issues(text, translated)
        if not issues:
            return translated
        self._record_quality("nllb_retries", issues)
        translated = self._nllb_translate(text, strict=True)
        issues = translation_quality_issues(text, translated)
        if issues:
            self._record_quality("quality_failures", issues)
            return ""
        return translated

    def translate(self, text: str, words: list[str], demo_thai: str = "") -> tuple[str, dict[str, str]]:
        key = translation_cache_key(text, self.config)
        if key in self.cache:
            row = self.cache[key]
            cache_issues = [] if self.config["demo"] else translation_quality_issues(text, row.get("thai_text", ""))
            if cache_issues:
                self._record_quality("cache_rejections", cache_issues)
                self.cache.pop(key, None)
                atomic_json(TRANSLATION_CACHE_PATH, self.cache)
            elif all(word in row.get("words", {}) for word in words):
                return row["thai_text"], safe_word_translations(words, row.get("words", {}))
        if self.config["demo"]:
            dictionary = safe_word_translations(words)
            result = (demo_thai or "คำแปลภาษาไทยสำหรับบทความตัวอย่าง", dictionary)
            self.cache[key] = {"thai_text": result[0], "words": result[1]}
            atomic_json(TRANSLATION_CACHE_PATH, self.cache)
            return result
        if self.config["translation_provider"] == "nllb":
            result = (self._nllb_with_quality_retry(text), safe_word_translations(words))
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
            if not translated and self.config["translation_provider"] == "auto":
                article_translation = self._nllb_with_quality_retry(text)
                translated = [article_translation, *("" for _ in words)] if article_translation else None
        if not translated or len(translated) != len(words) + 1:
            result = ("", safe_word_translations(words))
        else:
            result = (
                normalize_paragraphs(translated[0]),
                safe_word_translations(words, {word: normalize(value) for word, value in zip(words, translated[1:])}),
            )
        result_issues = translation_quality_issues(text, result[0])
        if result_issues:
            self._record_quality("quality_failures", result_issues)
            result = ("", result[1])
        self.cache[key] = {"thai_text": result[0], "words": result[1]}
        atomic_json(TRANSLATION_CACHE_PATH, self.cache)
        return result

    def _nllb_translate(self, text: str, strict: bool = False) -> str:
        try:
            import torch  # type: ignore
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # type: ignore

            if self._nllb_tokenizer is None or self._nllb_model is None:
                model_name = self.config["nllb_model"]
                logging.info("Loading local translation model %s", model_name)
                self._nllb_tokenizer = AutoTokenizer.from_pretrained(model_name, src_lang="eng_Latn")
                self._nllb_model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
                self._nllb_model.eval()
            target_id = self._nllb_tokenizer.convert_tokens_to_ids("tha_Thai")
            translated_paragraphs: list[str] = []
            paragraphs = [part for part in normalize_paragraphs(text).split("\n\n") if part]
            if not paragraphs:
                return ""
            for paragraph in paragraphs:
                translated_chunks: list[str] = []
                chunks = [
                    chunk for chunk in translation_chunks(paragraph, max_words=24 if strict else 45)
                    if not is_non_substantive_fragment(chunk)
                ]
                for chunk in chunks:
                    curated = exact_translated_phrase(chunk)
                    if curated:
                        translated_chunks.append(curated + ("" if curated[-1] in ".!?。！？" else "."))
                        continue
                    model_input = simplify_translation_source(chunk)
                    encoded = self._nllb_tokenizer(model_input, return_tensors="pt", truncation=True, max_length=512)
                    generation = {
                        "forced_bos_token_id": target_id, "max_length": 512,
                        "num_beams": 4 if strict else 3,
                    }
                    if strict:
                        generation.update({"no_repeat_ngram_size": 3, "repetition_penalty": 1.15, "early_stopping": True})
                    with torch.inference_mode():
                        generated = self._nllb_model.generate(**encoded, **generation)
                    decoded = normalize(self._nllb_tokenizer.batch_decode(generated, skip_special_tokens=True)[0])
                    if not re.search(r"[\u0e00-\u0e7f]", decoded):
                        return ""
                    if decoded[-1] not in ".!?。！？":
                        decoded += "."
                    translated_chunks.append(decoded)
                if translated_chunks:
                    translated_paragraphs.append(" ".join(translated_chunks))
            translated = normalize_paragraphs("\n\n".join(translated_paragraphs))
            return normalize_paragraphs(repair_translated_facts(text, translated))
        except (ImportError, OSError, RuntimeError, ValueError, AttributeError) as error:
            logging.error("Local NLLB translation failed: %s", error)
            return ""

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


def translation_cache_key(text: str, config: dict[str, Any]) -> str:
    provider = "demo" if config.get("demo") else config.get("translation_provider", "auto")
    model = config.get("nllb_model", "") if provider == "nllb" else ""
    payload = f"v{TRANSLATION_CACHE_VERSION}|{provider}|{model}|{text}"
    return hashlib.sha256(payload.encode()).hexdigest()


def translation_chunks(text: str, max_words: int = 45) -> list[str]:
    chunks: list[str] = []
    for sentence in sentence_split(text):
        words = sentence.split()
        for start in range(0, len(words), max_words):
            chunks.append(" ".join(words[start:start + max_words]))
    return chunks or [text]


def is_non_substantive_fragment(text: str) -> bool:
    words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text)
    if len(words) < 3:
        return True
    return len(words) <= 10 and bool(re.search(
        r"\b(?:caption|photo credit|image credit|AFP|Getty Images|Reuters)\b", text, re.I,
    ))


def image_query(article: dict[str, Any]) -> str:
    entities = re.findall(r"\b(?:[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+){0,2})\b", article["title"])
    words = [
        word.lower() for word in re.findall(r"[A-Za-z]{3,}", f"{article['title']} {article['category']}")
        if word.lower() not in STOPWORDS
    ]
    terms: list[str] = []
    for term in [article["category"], *entities, *words]:
        if term.lower() not in {item.lower() for item in terms}:
            terms.append(term)
    return " ".join(terms[:8]) or article["category"]


def image_relevance_score(article: dict[str, Any], query: str, candidate_text: str, source_weight: int) -> int:
    target = set(re.findall(r"[a-z]{3,}", f"{article['title']} {article['category']} {query}".lower())) - STOPWORDS
    candidate = set(re.findall(r"[a-z]{3,}", normalize(candidate_text).lower())) - STOPWORDS
    overlap = len(target & candidate)
    return min(100, source_weight + overlap * 8)


def image_record(
    article: dict[str, Any], query: str, *, url: str = "", local_filename: str = "",
    source: str, author: str, license_name: str, attribution_url: str, score: int,
    reason: str, is_fallback: bool = False, alt: str = "",
) -> dict[str, Any]:
    local_path = f"static/images/{local_filename}" if local_filename else ""
    return {
        "cache_version": IMAGE_CACHE_VERSION,
        "url": url,
        "local_filename": local_filename,
        "image_url": url or local_path,
        "image_local_path": local_path,
        "image_source": source,
        "image_author": author,
        "image_license": license_name,
        "image_attribution_url": attribution_url,
        "image_alt": alt or f"Cover image for {article['title']}",
        "image_query": query,
        "image_relevance_score": score,
        "image_selected_reason": reason,
        "image_is_fallback": is_fallback,
        "credit": author or source,
        "credit_url": attribution_url,
    }


def unique_fallback_image(article: dict[str, Any], query: str, reason: str) -> dict[str, Any]:
    filename = f"fallback-{article['id'][:12]}.svg"
    output = STATIC_DIR / "images" / filename
    output.parent.mkdir(parents=True, exist_ok=True)
    hue = int(article["id"][:6], 16) % 360
    keywords = [html.escape(word) for word in query.split()[:4]]
    label = " / ".join(keywords) or html.escape(article["category"])
    title = html.escape(article["title"][:92])
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="800" viewBox="0 0 1400 800" role="img" aria-labelledby="title desc">
<title id="title">{title}</title><desc id="desc">Unique local cover for {title}</desc>
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="hsl({hue},55%,26%)"/><stop offset="1" stop-color="hsl({(hue + 55) % 360},62%,52%)"/></linearGradient></defs>
<rect width="1400" height="800" fill="url(#g)"/><circle cx="1160" cy="140" r="260" fill="white" opacity=".11"/><circle cx="160" cy="720" r="330" fill="black" opacity=".12"/>
<text x="90" y="130" fill="white" opacity=".78" font-family="Georgia,serif" font-size="34">{html.escape(article['category'].upper())}</text>
<text x="90" y="590" fill="white" font-family="Georgia,serif" font-size="58" font-weight="700">{label}</text>
<text x="90" y="665" fill="white" opacity=".8" font-family="Arial,sans-serif" font-size="26">Daily English Reader</text></svg>'''
    output.write_text(svg, encoding="utf-8")
    return image_record(
        article, query, local_filename=filename, source="Local generated SVG", author="Daily English Reader",
        license_name="Project-owned local asset", attribution_url="", score=20,
        reason=reason, is_fallback=True,
    )


def source_page_image(article: dict[str, Any], session: requests.Session, config: dict[str, Any]) -> dict[str, str]:
    try:
        response = session.get(article["url"], headers={"User-Agent": USER_AGENT}, timeout=config["timeout"])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        node = soup.select_one('meta[property="og:image"], meta[name="twitter:image"]')
        if not node or not node.get("content"):
            return {}
        alt_node = soup.select_one('meta[property="og:image:alt"], meta[name="twitter:image:alt"]')
        return {"url": node["content"], "alt": alt_node.get("content", "") if alt_node else ""}
    except requests.RequestException:
        return {}


def source_media_license(article: dict[str, Any]) -> str:
    return {
        "NASA": "NASA Media Usage Guidelines",
        "USGS": "U.S. government public-domain media",
        "US National Weather Service": "U.S. government public-domain media",
    }.get(article.get("provider", ""), "")


def cache_image_or_fallback(
    article: dict[str, Any], result: dict[str, Any], session: requests.Session,
    config: dict[str, Any], query: str, fallback_on_error: bool = True,
) -> dict[str, Any] | None:
    if result.get("local_filename"):
        return result
    url = result.get("url", "")
    if not url:
        return unique_fallback_image(article, query, "No usable free image candidate") if fallback_on_error else None
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
        result["local_filename"] = filename
        result["image_local_path"] = f"static/images/{filename}"
        result["image_url"] = result["image_local_path"]
        return result
    except (requests.RequestException, ValueError, OSError) as error:
        logging.info("Image cache failed for %s: %s", article["title"], error)
        if fallback_on_error:
            return unique_fallback_image(article, query, f"Selected image was unavailable: {type(error).__name__}")
        return None


def local_generated_image(
    article: dict[str, Any], query: str, session: requests.Session, config: dict[str, Any],
) -> dict[str, Any] | None:
    if not config.get("local_image_url"):
        return None
    try:
        endpoint = f"{config['local_image_url'].rstrip('/')}/sdapi/v1/txt2img"
        response = session.post(endpoint, json={
            "prompt": (
                f"Realistic editorial news photograph about {article['title']}. "
                f"Context: {article['description'][:400]}. Natural light, accurate details, "
                "landscape composition, no text, no logo, no watermark."
            ),
            "negative_prompt": "text, caption, logo, watermark, poster, cartoon, blurry",
            "width": 1024, "height": 576, "steps": config.get("local_image_steps", 20),
        }, timeout=config.get("local_image_timeout", 180))
        response.raise_for_status()
        encoded = (response.json().get("images") or [])[0].split(",", 1)[-1]
        image_bytes = base64.b64decode(encoded, validate=True)
        if len(image_bytes) < 10_000:
            raise ValueError("Local image response was too small")
        filename = f"generated-{article['id']}.png"
        output = STATIC_DIR / "images" / filename
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(image_bytes)
        return image_record(
            article, query, local_filename=filename, source="Local Stable Diffusion",
            author="Generated locally", license_name="Project-owned local generation", attribution_url="",
            score=40, reason="Generated locally after free image sources returned no usable result",
        )
    except (requests.RequestException, ValueError, KeyError, IndexError, json.JSONDecodeError) as error:
        logging.warning("Local image generator unavailable for %s: %s", article["title"], error)
        return None


def openverse_tag_text(tags: Any) -> str:
    if isinstance(tags, str):
        return tags
    if not isinstance(tags, list):
        return ""
    values: list[str] = []
    for tag in tags:
        if isinstance(tag, str):
            values.append(tag)
        elif isinstance(tag, dict):
            value = tag.get("name") or tag.get("text") or tag.get("label")
            if isinstance(value, str):
                values.append(value)
    return " ".join(values)


def image_for(
    article: dict[str, Any], session: requests.Session, quota: QuotaManager, config: dict[str, Any],
) -> dict[str, Any]:
    cache = load_json(IMAGE_CACHE_PATH, {})
    query = image_query(article)
    used: set[str] = config.setdefault("_used_image_urls", set())

    def track_selection(result: dict[str, Any]) -> None:
        if result.get("image_is_fallback"):
            quota.skipped("images", result.get("image_selected_reason") or "local fallback image")
            return
        provider = {
            "Openverse": "openverse",
            "Wikimedia Commons": "commons",
            "Unsplash": "unsplash",
            "Local Stable Diffusion": "local-images",
        }.get(result.get("image_source"), "source-images")
        quota.selected(provider)
    cached = cache.get(article["id"], {})
    local_name = cached.get("local_filename")
    cache_identity = cached.get("url") or local_name
    if (
        cached.get("cache_version") == IMAGE_CACHE_VERSION
        and local_name and (STATIC_DIR / "images" / local_name).exists()
        and cache_identity not in used
    ):
        used.add(cache_identity)
        return cached
    if config.get("demo", False):
        filename = DEMO_IMAGE_MAP.get(article["title"])
        result = image_record(
            article, query, local_filename=filename or f"fallback-{article['id'][:12]}.svg",
            source="Bundled demo asset", author="Daily English Reader", license_name="Project-owned local asset",
            attribution_url="", score=80 if filename else 20, reason="Curated demo topic image",
            is_fallback=not bool(filename),
        ) if filename else unique_fallback_image(article, query, "No curated demo image")
        cache[article["id"]] = result
        atomic_json(IMAGE_CACHE_PATH, cache)
        used.add(result.get("local_filename", ""))
        track_selection(result)
        return result

    candidates: list[dict[str, Any]] = []
    source_license = source_media_license(article)
    if article.get("image_url") and source_license:
        candidates.append(image_record(
            article, query, url=article["image_url"], source=article["provider"],
            author=article.get("author") or article["provider"], license_name=source_license,
            attribution_url=article["url"], score=95, reason="Image supplied by the RSS/source feed",
        ))
    source_image = source_page_image(article, session, config) if source_license else {}
    if source_image:
        candidates.append(image_record(
            article, query, url=source_image["url"], source=article["provider"],
            author=article.get("author") or article["provider"], license_name=source_license,
            attribution_url=article["url"], score=88, reason="Source page og:image",
            alt=source_image.get("alt", ""),
        ))

    for source_candidate in sorted(candidates, key=lambda row: row["image_relevance_score"], reverse=True):
        if source_candidate.get("url") in used:
            continue
        source_result = cache_image_or_fallback(
            article, source_candidate, session, config, query, fallback_on_error=False,
        )
        if source_result:
            identity = source_result.get("url") or source_result.get("local_filename", "")
            if identity:
                used.add(identity)
            cache[article["id"]] = source_result
            atomic_json(IMAGE_CACHE_PATH, cache)
            track_selection(source_result)
            return source_result
    candidates = []

    def add_openverse() -> None:
        try:
            payload = request_json(session, quota, "openverse", OPENVERSE_URL, params={
                "q": query, "page_size": 8, "license_type": "commercial",
            }, timeout=config["timeout"])
            for row in payload.get("results", []):
                url = row.get("url") or row.get("thumbnail", "")
                text = f"{row.get('title', '')} {openverse_tag_text(row.get('tags'))}"
                candidates.append(image_record(
                    article, query, url=url, source="Openverse", author=row.get("creator") or "Openverse contributor",
                    license_name=" ".join(filter(None, [row.get("license", ""), row.get("license_version", "")])),
                    attribution_url=row.get("foreign_landing_url") or "https://openverse.org/",
                    score=image_relevance_score(article, query, text, 55), reason="Best relevant Openverse result",
                    alt=row.get("title", ""),
                ))
        except ProviderError:
            pass

    def add_commons() -> None:
        try:
            payload = request_json(session, quota, "commons", COMMONS_URL, params={
                "action": "query", "generator": "search", "gsrsearch": query, "gsrnamespace": 6,
                "gsrlimit": 8, "prop": "imageinfo", "iiprop": "url|extmetadata", "format": "json",
            }, timeout=config["timeout"])
            for page in payload.get("query", {}).get("pages", {}).values():
                info = (page.get("imageinfo") or [{}])[0]
                meta = info.get("extmetadata", {})
                value = lambda name: normalize(meta.get(name, {}).get("value", ""))
                candidates.append(image_record(
                    article, query, url=info.get("url", ""), source="Wikimedia Commons",
                    author=value("Artist") or "Wikimedia Commons contributor",
                    license_name=value("LicenseShortName") or "Wikimedia Commons license",
                    attribution_url=info.get("descriptionurl", "https://commons.wikimedia.org/"),
                    score=image_relevance_score(article, query, f"{page.get('title', '')} {value('ImageDescription')}", 50),
                    reason="Best relevant Wikimedia Commons result", alt=value("ImageDescription"),
                ))
        except ProviderError:
            pass

    add_openverse()
    add_commons()
    if config.get("unsplash_key"):
        try:
            payload = request_json(session, quota, "unsplash", UNSPLASH_URL, params={
                "query": query, "per_page": 8, "page": 1, "orientation": "landscape",
            }, headers={"Authorization": f"Client-ID {config['unsplash_key']}", "Accept-Version": "v1"},
                timeout=config["timeout"])
            for photo in payload.get("results", []):
                user = photo.get("user", {})
                candidates.append(image_record(
                    article, query,
                    url=add_query(photo["urls"]["raw"], {"w": "1400", "h": "800", "fit": "crop", "q": "78"}),
                    source="Unsplash", author=user.get("name", "Unsplash contributor"),
                    license_name="Unsplash License",
                    attribution_url=add_query(user.get("links", {}).get("html", "https://unsplash.com"), {
                        "utm_source": "daily_english_reader", "utm_medium": "referral",
                    }),
                    score=image_relevance_score(article, query, photo.get("description") or photo.get("alt_description", ""), 45),
                    reason="Best relevant Unsplash free-key result", alt=photo.get("alt_description", ""),
                ))
        except (ProviderError, KeyError):
            pass
    else:
        quota.disable("unsplash", "missing optional free access key")

    candidates = [
        row for row in candidates
        if row.get("url") and row["url"] not in used
        and row.get("image_author") and row.get("image_license") and row.get("image_attribution_url")
    ]
    candidates.sort(key=lambda row: row["image_relevance_score"], reverse=True)
    local_result = local_generated_image(article, query, session, config) if not candidates else None
    result = cache_image_or_fallback(
        article, candidates[0] if candidates else (local_result or {}), session, config, query,
    )
    if result is None:
        result = unique_fallback_image(article, query, "No usable free image candidate")
    identity = result.get("url") or result.get("local_filename", "")
    if identity:
        used.add(identity)
    cache[article["id"]] = result
    atomic_json(IMAGE_CACHE_PATH, cache)
    track_selection(result)
    return result


def source_material(raw: dict[str, Any], session: requests.Session, config: dict[str, Any]) -> str:
    """Use source-page paragraphs when available, otherwise keep the feed summary."""
    fallback = raw["description"]
    if raw.get("isFallback"):
        return fallback
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
        seen: set[str] = set()
        for node in soup.select("article p, main p, [role='main'] p, p"):
            if node.find_parent(["figure", "figcaption"]):
                continue
            nearby = [node, *list(node.parents)[:2]]
            markers = " ".join(
                " ".join(parent.get("class", [])) + " " + str(parent.get("id", ""))
                for parent in nearby if getattr(parent, "get", None)
            )
            if re.search(r"\b(caption|credit|image-data|photo-credit)\b", markers, re.I):
                continue
            text = clean_story_text(node.get_text(" "))
            if (
                len(text.split()) >= 8
                and text not in seen
                and not re.search(r"\b(subscribe|sign up|cookie|newsletter)\b", text, re.I)
            ):
                paragraphs.append(text)
                seen.add(text)
            if sum(len(row.split()) for row in paragraphs) >= 420:
                break
        material = " ".join(paragraphs)
        if len(material.split()) >= 80:
            # The feed summary is usually clean and prevents caption-heavy pages
            # from dominating the deterministic extractive summary.
            return clean_story_text(f"{fallback} {material}")
    except requests.RequestException as error:
        logging.info("Source-page text unavailable for %s: %s", raw["title"], error)
    return fallback


def naturalize_thai(text: str) -> str:
    text = normalize_paragraphs(text)
    replacements = {
        "ได้กล่าวว่า": "บอกว่า",
        "กล่าวว่า": "บอกว่า",
        "ข่มขืนสิทธิมนุษยชน": "ละเมิดสิทธิมนุษยชน",
        "หินหินใหญ่ขนาดเปียก": "ลูกเห็บขนาดเล็ก",
        "น.ม.": "น.",
        "ประชาชน": "ผู้คน",
        "สามารถ": "ทำได้",
        "เนื่องจาก": "เพราะ",
        "อย่างไรก็ตาม": "แต่",
        "ในขณะที่": "ขณะที่",
        "ดังกล่าว": "นี้",
        "รายงานว่า": "รายงานว่า",
        "ผลิตภัณฑ์ประจําเดือน": "ผลิตภัณฑ์สำหรับประจำเดือน",
        "กระดาษประจําเดือน": "ผ้าอนามัย",
        "สาปิสุขภาพ": "ผ้าอนามัย",
        "ถูกภาษีเป็นสินค้าหรูหรา": "ถูกเก็บภาษีในฐานะสินค้าฟุ่มเฟือย",
        "คนหลายคน": "หลายคน",
        "ประจํา": "ประจำ",
        "สําหรับ": "สำหรับ",
        "ทํา": "ทำ",
    }
    for formal, natural in replacements.items():
        text = text.replace(formal, natural)
    text = re.sub(r"\bknots?\b", "นอต", text, flags=re.I)
    paragraphs = []
    for paragraph in text.split("\n\n"):
        paragraph = re.sub(r"([.!?])(?=[\u0e00-\u0e7f])", r"\1 ", paragraph)
        paragraph = re.sub(r"\s+([,.!?])", r"\1", paragraph)
        paragraphs.append(re.sub(r"\s{2,}", " ", paragraph).strip())
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


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
        import pyttsx3

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
    text = prepare_reader_text(adapt_level(material, raw["level"], config, session))
    speech_text = make_speech_text(raw["title"], text)
    speech_issues = speech_text_issues(speech_text)
    if speech_issues:
        raise RuntimeError(f"Unsafe Web Speech text for article {raw['id']}: {', '.join(speech_issues)}")
    words = vocabulary_words(text)
    translated_thai, translations = translator.translate(text, words, raw.get("thai_demo", ""))
    if config["require_full_translation"] and not is_useful_thai_translation(text, translated_thai):
        raise RuntimeError(f"Full Thai translation unavailable for article {raw['id']}")
    thai_text = full_thai_article(raw, text, translated_thai)
    translations = safe_word_translations(words, translations)
    word_pos = {word: part_of_speech(word) for word in words}
    audio_path = generate_audio(text, raw["id"], raw["level"], published_date, config)
    image = image_for(raw, session, quota, config)
    slug = f"{slugify(raw['title'])}-{raw['id'][:8]}"
    is_fallback = bool(raw.get("isFallback", False))
    return {
        "schema_version": SCHEMA_VERSION, "id": raw["id"], "slug": slug, "level": raw["level"],
        "title": raw["title"], "description": raw["description"], "text": text,
        "speech_text": speech_text, "thai_text": thai_text,
        "word_translations": translations, "category": raw["category"], "provider": raw["provider"],
        "word_pos": word_pos,
        "content_type": raw["content_type"], "source_url": raw["url"], "author": raw["author"],
        "isFallback": is_fallback,
        "isRealNews": False if is_fallback else raw.get("provider") != "demo",
        "contentType": PRACTICE_CONTENT_TYPE if is_fallback else "news_article",
        "sourceName": raw.get("sourceName") or raw["provider"],
        "disclaimerEn": raw.get("disclaimerEn", ""),
        "disclaimerTh": raw.get("disclaimerTh", ""),
        "published": raw["published"], "published_date": published_date, "image": image,
        "audio_cache_path": str(audio_path.relative_to(ROOT)).replace("\\", "/"),
        "generated_at": utc_now().isoformat(),
    }


def validate_processed_article(row: dict[str, Any], level: str) -> None:
    if row.get("schema_version") != SCHEMA_VERSION:
        raise RuntimeError(f"Processed article does not use schema {SCHEMA_VERSION}")
    if row.get("level") != level:
        raise RuntimeError(f"Processed article changed level from {level}")
    if not row.get("speech_text") or speech_text_issues(row.get("speech_text", "")):
        raise RuntimeError("Processed article contains unsafe Web Speech text")
    if not is_useful_thai_translation(row.get("text", ""), article_translation_body(row)):
        raise RuntimeError("Processed article contains incomplete or placeholder Thai translation")
    if row.get("isFallback"):
        issues = fallback_metadata_issues(row)
        if issues:
            raise RuntimeError(f"Fallback metadata invalid: {', '.join(issues)}")
    elif row.get("provider") != "demo" and (
        row.get("isRealNews") is not True or row.get("contentType") != "news_article"
    ):
        raise RuntimeError("Real-news metadata invalid")


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


def article_meets_current_quality(row: dict[str, Any]) -> bool:
    if row.get("schema_version") != SCHEMA_VERSION or not row.get("speech_text"):
        return False
    if speech_text_issues(row.get("speech_text", "")):
        return False
    if row.get("provider") == "demo":
        return True
    return not translation_quality_issues(row.get("text", ""), article_translation_body(row))


def load_articles(retention_days: int) -> list[dict[str, Any]]:
    cutoff = utc_now() - timedelta(days=retention_days)
    articles = []
    for path in PROCESSED_DIR.glob("*/*.json"):
        row = load_json(path, None)
        if row and article_meets_current_quality(row) and parse_date(row.get("generated_at")) >= cutoff:
            articles.append(row)
    return sorted(articles, key=lambda row: parse_date(row["generated_at"]), reverse=True)


def load_articles_any_schema(retention_days: int) -> list[dict[str, Any]]:
    cutoff = utc_now() - timedelta(days=retention_days)
    articles = []
    for path in PROCESSED_DIR.glob("*/*.json"):
        row = load_json(path, None)
        if row and parse_date(row.get("generated_at")) >= cutoff:
            articles.append(row)
    return sorted(articles, key=lambda row: parse_date(row["generated_at"]), reverse=True)


def processed_to_source(article: dict[str, Any]) -> dict[str, Any]:
    image = article.get("image", {})
    return {
        "id": article["id"], "provider": article["provider"], "provider_key": slugify(article["provider"], 32),
        "title": article["title"], "description": article["description"],
        "url": article.get("source_url", ""), "category": article["category"],
        "published": article["published"], "author": article.get("author", ""),
        "content_type": article.get("content_type", "news"),
        "image_url": image.get("url", ""), "thai_demo": "", "level": article["level"],
        "isFallback": article.get("isFallback", False),
        "isRealNews": article.get("isRealNews", True),
        "contentType": article.get("contentType", "news_article"),
        "sourceName": article.get("sourceName", article["provider"]),
        "disclaimerEn": article.get("disclaimerEn", ""),
        "disclaimerTh": article.get("disclaimerTh", ""),
    }


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
        "image_alt": image.get("image_alt") or f"Cover image for {article['title']}",
        "published_display": parse_date(article["published"]).strftime("%d %b %Y"),
        "word_html": word_spans(article["text"], article["word_translations"], article.get("word_pos", {})),
        "thai_paragraphs": [part for part in article.get("thai_text", "").split("\n\n") if part.strip()],
        "audio_source": audio_source,
    }


def render_site(
    articles: list[dict[str, Any]], quota: QuotaManager, expected_date: str,
    build_report: dict[str, Any],
) -> None:
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    shutil.copytree(STATIC_DIR, STAGING_DIR / "static")
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html"]))
    common = {
        "description": "Free daily English news practice for Thai learners.",
        "updated_at": utc_now().astimezone().strftime("%d %b %Y, %H:%M"),
    }
    today = expected_date
    recent_cutoff = datetime.fromisoformat(expected_date).date() - timedelta(days=6)
    site_articles = [
        row for row in articles
        if recent_cutoff <= parse_date(row["published_date"]).date() <= datetime.fromisoformat(expected_date).date()
    ]
    views = [article_view(article, "") for article in site_articles]
    recent = list(views)
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
    for article in site_articles:
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
            "isFallback": article.get("isFallback", False),
            "isRealNews": article.get("isRealNews", True),
            "contentType": article.get("contentType", "news_article"),
        })
    atomic_json(STAGING_DIR / "content-index.json", content_index)
    provider_status = quota.public_status(
        demo_fallback_blocked=not bool(build_report.get("demo_mode")),
        expected_date=expected_date,
    )
    build_report.update({
        "status": "ready", "completed_at": utc_now().isoformat(), "latest_date": expected_date,
        "total_story_count": len(content_index), "today_story_count": len(today_views),
        "level_distribution": dict(Counter(row["level"] for row in today_views)),
        "schema_version": SCHEMA_VERSION,
        "fallback_image_count": sum(bool(row["image"].get("image_is_fallback")) for row in today_views),
        "fallback_images": [
            {
                "article_id": row["id"],
                "title": row["title"],
                "reason": row["image"].get("image_selected_reason", ""),
            }
            for row in today_views if row["image"].get("image_is_fallback")
        ],
    })
    atomic_json(PROVIDER_STATUS_PATH, provider_status)
    atomic_json(BUILD_REPORT_PATH, build_report)
    atomic_json(STAGING_DIR / "provider-status.json", provider_status)
    atomic_json(STAGING_DIR / "build-report.json", build_report)
    validate_staging(today_views, expected_date, allow_demo=bool(build_report.get("demo_mode")))
    validate_internal_links_and_secrets()
    atomic_publish()


def validate_staging(
    today_articles: list[dict[str, Any]], expected_date: str | None = None, *, allow_demo: bool = False,
) -> None:
    expected_date = expected_date or expected_edition_date()
    if len(today_articles) != DAILY_ARTICLE_COUNT:
        raise RuntimeError(f"Expected {DAILY_ARTICLE_COUNT} current articles, got {len(today_articles)}")
    if any(row.get("published_date") != expected_date for row in today_articles):
        raise RuntimeError(f"Current edition date does not match Toronto date {expected_date}")
    if Counter(row["level"] for row in today_articles) != Counter({level: TARGET_PER_LEVEL for level in LEVELS}):
        raise RuntimeError("Current articles are not split 2 per level")
    if not allow_demo and any(row.get("provider") == "demo" for row in today_articles):
        raise RuntimeError("Demo-only article reached production validation")
    if not allow_demo:
        for row in today_articles:
            if row.get("isFallback"):
                issues = fallback_metadata_issues(row)
                if issues:
                    raise RuntimeError(f"Fallback article metadata is invalid: {', '.join(issues)}")
            elif row.get("isRealNews") is not True or row.get("contentType") != "news_article":
                raise RuntimeError("Real-news article metadata is invalid")
    if any(row.get("schema_version") != SCHEMA_VERSION for row in today_articles):
        raise RuntimeError(f"Current articles must use schema {SCHEMA_VERSION}")
    if any(not row.get("speech_text") or speech_text_issues(row.get("speech_text", "")) for row in today_articles):
        raise RuntimeError("Current edition contains unsafe Web Speech text")
    if not allow_demo and any(
        not is_useful_thai_translation(row.get("text", ""), article_translation_body(row))
        for row in today_articles
    ):
        raise RuntimeError("Current edition contains incomplete or placeholder Thai translation")
    image_fields = {
        "image_url", "image_local_path", "image_source", "image_author", "image_license",
        "image_attribution_url", "image_alt", "image_query", "image_relevance_score",
        "image_selected_reason", "image_is_fallback",
    }
    if any(not image_fields.issubset(row.get("image", {})) for row in today_articles):
        raise RuntimeError("Current edition contains incomplete image metadata")
    identities = [row["image"].get("url") or row["image"].get("local_filename") for row in today_articles]
    if len(identities) != len(set(identities)):
        raise RuntimeError("Current edition contains duplicate cover images")
    required = [
        "index.html", "daily.html", "vocabulary.html", "flashcards.html", "saved.html",
        "content-index.json", "provider-status.json", "build-report.json",
    ]
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
            if not any(path.stat().st_size >= 400 for path in audio_files):
                raise RuntimeError(f"Missing readable audio fallback for {article['id']}")


def validate_internal_links_and_secrets() -> None:
    root = STAGING_DIR.resolve()
    broken: list[str] = []
    for page in STAGING_DIR.rglob("*.html"):
        soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
        for node, attribute in [(node, "href") for node in soup.select("[href]")] + [
            (node, "src") for node in soup.select("[src]")
        ]:
            value = node.get(attribute, "").strip()
            parsed = urlparse(value)
            if not value or value.startswith(("#", "data:", "mailto:", "tel:", "javascript:")) or parsed.scheme:
                continue
            path_text = unquote(parsed.path)
            if path_text.lstrip("./").startswith("podcast/"):
                continue
            target = (root / path_text.lstrip("/")) if path_text.startswith("/") else (page.parent / path_text)
            target = target.resolve()
            if root not in target.parents and target != root:
                broken.append(f"{page.relative_to(root)} -> {value}")
                continue
            if target.is_dir():
                target = target / "index.html"
            if not target.exists():
                broken.append(f"{page.relative_to(root)} -> {value}")
    if broken:
        raise RuntimeError(f"Broken internal links: {broken[:8]}")
    secret_patterns = re.compile(r"cfat_[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|BEGIN PRIVATE KEY|google-tts-api-key", re.I)
    for path in STAGING_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".html", ".js", ".json", ".css", ".txt"}:
            if secret_patterns.search(path.read_text(encoding="utf-8", errors="ignore")):
                raise RuntimeError(f"Possible secret found in built site: {path.relative_to(root)}")


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
    cutoff = toronto_now().date() - timedelta(days=retention_days)
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
        "require_full_translation": env_bool("REQUIRE_FULL_TRANSLATION", False),
        "translation_provider": os.getenv("READING_TRANSLATION_PROVIDER", "auto").strip().lower(),
        "nllb_model": os.getenv("READING_TRANSLATION_MODEL", "facebook/nllb-200-distilled-600M").strip(),
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
    today_date = toronto_now().date()
    today = today_date.isoformat()
    build_report: dict[str, Any] = {
        "status": "running", "started_at": utc_now().isoformat(), "expected_toronto_date": today,
        "free_only": True, "demo_mode": config["demo"], "demo_fallback_blocked": not config["demo"],
        "skip_audio": config["skip_audio"], "required_story_count": DAILY_ARTICLE_COUNT,
        "required_levels": {level: TARGET_PER_LEVEL for level in LEVELS}, "schema_version": SCHEMA_VERSION,
        "candidate_rejections": [], "practice_fallback_count": 0,
    }
    try:
        retained_articles = load_articles(config["retention_days"])
        all_retained_articles = load_articles_any_schema(config["retention_days"])
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
        candidates: list[dict[str, Any]] = []
        translator: Translator | None = None
        if dates_to_build:
            needs_fresh_candidates = any(
                target_date == today
                or len([row for row in all_retained_articles if row["published_date"] == target_date]) != DAILY_ARTICLE_COUNT
                for target_date in dates_to_build
            )
            if needs_fresh_candidates:
                candidates = collect_candidates(session, quota, config)
                atomic_json(RAW_DIR / f"{today}-providers.json", {
                    "fetched_at": utc_now().isoformat(), "candidates": candidates,
                })
            translator = Translator(session, config)
            for date_index, target_date in enumerate(dates_to_build):
                historic = [row for row in all_retained_articles if row["published_date"] == target_date]
                if target_date != today and len(historic) == DAILY_ARTICLE_COUNT:
                    selected = [processed_to_source(row) for row in historic]
                    logging.info("Rebuilding %s from its existing real story selection", target_date)
                else:
                    selected = choose_daily_articles(candidates, offset=date_index * DAILY_ARTICLE_COUNT)
                config["_used_image_urls"] = set()
                selected_ids = {row["id"] for row in selected}
                processed: list[dict[str, Any]] = []
                for level in LEVELS:
                    level_selected = [row for row in selected if row["level"] == level]
                    logging.info("[%s] Building %s readings from real news first", target_date, level)
                    processed.extend(build_level_readings(
                        level, level_selected, candidates, selected_ids, session, quota, translator,
                        config, target_date, build_report, offset=date_index * DAILY_ARTICLE_COUNT,
                    ))
                if target_date == today:
                    for row in candidates:
                        if row["id"] not in selected_ids:
                            quota.skipped(row.get("provider_key", slugify(row["provider"], 32)), "not selected for daily edition")
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
        if translator is not None:
            build_report["translation_quality"] = translator.diagnostics_summary()
        articles = load_articles(config["retention_days"])
        render_site(articles, quota, today, build_report)
        logging.info("Published %d retained article(s).", len(articles))
        return 0
    except Exception as error:
        if "translator" in locals() and translator is not None:
            build_report["translation_quality"] = translator.diagnostics_summary()
        build_report.update({"status": "failed", "completed_at": utc_now().isoformat(), "error": str(error)[:500]})
        atomic_json(PROVIDER_STATUS_PATH, quota.public_status(
            demo_fallback_blocked=not bool(build_report.get("demo_mode")),
            expected_date=build_report.get("expected_toronto_date"),
        ))
        atomic_json(BUILD_REPORT_PATH, build_report)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        logging.error("%s", error)
        raise SystemExit(1)
