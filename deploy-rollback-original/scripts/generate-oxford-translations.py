#!/usr/bin/env python
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from deep_translator import GoogleTranslator
from deep_translator.exceptions import TranslationNotFound

APP_ROOT = Path(__file__).resolve().parent.parent
APP_JS = APP_ROOT / "app.js"
OXFORD_TXT = APP_ROOT / "oxford3000.txt"
OUTPUT = APP_ROOT / "oxford-translations.json"


def clean_word(raw):
    return re.sub(r"[^\w\s.'-]", "", re.sub(r"\s+[12]$", "", raw)).strip()


def load_thai_pack():
    node_script = r"""
const fs = require("fs");
const vm = require("vm");
const code = fs.readFileSync("deploy-rollback-original/app.js", "utf8");
const start = code.indexOf("const thaiPack = {");
const end = code.indexOf("};\n\nconst categoryOrder", start);
const snippet = code.slice(start, end + 2);
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(snippet + "; globalThis.out = thaiPack;", sandbox);
console.log(JSON.stringify(sandbox.out));
"""
    return json.loads(
        subprocess.check_output(
            ["node", "-e", node_script],
            cwd=str(APP_ROOT.parent),
            text=True,
            encoding="utf8"
        )
    )


def load_oxford_words():
    words = []
    seen = set()
    for raw in OXFORD_TXT.read_text(encoding="utf8").splitlines():
        word = clean_word(raw)
        if not word:
            continue
        lower = word.lower()
        if lower in seen:
            continue
        seen.add(lower)
        words.append(word)
    return words


def normalize_thai_meaning(text):
    value = re.sub(r"\s+", " ", str(text).strip())
    value = value.replace(" หรือ ", ", ")
    value = value.replace("/", ", ")
    return value.strip(" ,")


def load_existing_entries():
    if not OUTPUT.exists():
        return {}
    try:
        payload = json.loads(OUTPUT.read_text(encoding="utf8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload.get("entries", {})


def translate_meaning(translator, word):
    candidates = [word, word.replace("-", " "), word.replace(".", " ").strip()]
    for candidate in candidates:
        if not candidate:
            continue
        for _ in range(3):
            try:
                translated = translator.translate(candidate)
                meaning = normalize_thai_meaning(translated)
                if meaning:
                    return meaning
            except TranslationNotFound:
                break
            except Exception:
                time.sleep(0.6)
        time.sleep(0.2)
    return ""


def build_payload(oxford_words, entries):
    preserved = sum(1 for item in entries.values() if item.get("source") == "thaiPack")
    translated = sum(1 for item in entries.values() if item.get("source") == "google-translate")
    unresolved = sum(1 for item in entries.values() if item.get("source") == "unresolved")
    return {
        "version": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceWordList": OXFORD_TXT.name,
        "translator": "deep-translator GoogleTranslator",
        "totalEntries": len(oxford_words),
        "preservedFromThaiPack": preserved,
        "translatedMissingEntries": translated,
        "unresolvedEntries": unresolved,
        "entries": entries
    }


def save_payload(oxford_words, entries):
    payload = build_payload(oxford_words, entries)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    return payload


def generate_payload():
    thai_pack = load_thai_pack()
    known = {key.lower(): row for key, row in thai_pack.items()}
    oxford_words = load_oxford_words()
    translator = GoogleTranslator(source="en", target="th")

    entries = load_existing_entries()

    for index, word in enumerate(oxford_words, start=1):
        lower = word.lower()
        if lower in entries:
            continue
        packed = known.get(lower)
        if packed:
            entries[lower] = {
                "word": word,
                "meaning": packed[1],
                "exampleTh": packed[3],
                "hasCuratedExample": True,
                "source": "thaiPack"
            }
            continue

        meaning = translate_meaning(translator, word)
        entries[lower] = {
            "word": word,
            "meaning": meaning or "ยังไม่มีคำแปลไทย",
            "exampleTh": "",
            "hasCuratedExample": False,
            "source": "google-translate" if meaning else "unresolved"
        }
        if index % 50 == 0:
            time.sleep(0.2)
        if index % 200 == 0:
            save_payload(oxford_words, entries)

    return build_payload(oxford_words, entries)


def main():
    payload = generate_payload()
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({
        "output": str(OUTPUT),
        "totalEntries": payload["totalEntries"],
        "preservedFromThaiPack": payload["preservedFromThaiPack"],
        "translatedMissingEntries": payload["translatedMissingEntries"],
        "unresolvedEntries": payload.get("unresolvedEntries", 0)
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
