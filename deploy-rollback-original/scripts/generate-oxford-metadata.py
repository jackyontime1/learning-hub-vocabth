#!/usr/bin/env python
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from transformers import pipeline
from wordfreq import zipf_frequency

APP_ROOT = Path(__file__).resolve().parent.parent
APP_JS = APP_ROOT / "app.js"
OXFORD_TXT = APP_ROOT / "oxford3000.txt"
OUTPUT = APP_ROOT / "oxford-metadata.json"

GENERAL_CATEGORIES = [
    "Starter Everyday",
    "Work & Study",
    "People & Feelings",
    "Travel & Places",
    "Home & Food",
    "Nature & Health",
    "Actions & Thinking",
    "Society & Media",
]

LABEL_DESCRIPTIONS = {
    "Starter Everyday": "basic everyday words, time words, numbers, function words, simple conversation",
    "Work & Study": "work, study, school, office, business, projects, learning",
    "People & Feelings": "people, relationships, emotions, personality, social life",
    "Travel & Places": "travel, transport, places, locations, directions, moving around",
    "Home & Food": "home, rooms, household objects, clothes, food, cooking",
    "Nature & Health": "body, health, medicine, animals, weather, environment, nature",
    "Actions & Thinking": "actions, decisions, problem solving, change, thinking, doing",
    "Society & Media": "culture, art, entertainment, news, technology, law, public life",
}

COMMON_ACTION_HEADS = {
    "be", "have", "do", "go", "say", "get", "make", "know", "think", "take",
    "see", "come", "want", "look", "use", "find", "give", "tell", "work",
    "call", "try", "ask", "need", "feel", "become", "leave", "put", "bring",
    "begin", "keep", "hold", "write", "read", "speak", "listen", "set", "run"
}


def ws(value):
    return set(value.split())


STARTER_EXACT = ws(
    "a an the and or but so if because as at by for from in into of on out over to up "
    "with without within after before during while when where who whom whose which what "
    "why how this that these those here there yes no not very too quite just already "
    "still yet again also maybe perhaps really always often sometimes never ever ago "
    "today tonight tomorrow yesterday morning afternoon evening night week month year "
    "first second third last next early late now then soon one two three four five six "
    "seven eight nine ten hundred thousand i me my mine myself you your yours yourself "
    "he him his himself she her hers herself it its itself we us our ours ourselves they "
    "them their theirs themselves someone anyone everybody nobody something anything "
    "nothing each either neither another other both all some any many much more most "
    "less least enough own same such no one one another somewhere anywhere therefore "
    "however although unless until upon onto"
)

KEYWORDS = {
    "Starter Everyday": ws(
        "hello thanks thank please okay maybe usually often never always today tomorrow "
        "yesterday morning evening night week month year minute hour time thing stuff "
        "way kind sort question answer number little big small good bad better best "
        "possible ready true false real sure simple hard easy difficult old young new "
        "first last next early late current recent daily normal whole full single "
        "double open close start end begin finish back front side around together apart "
        "again then here there common usual"
    ),
    "Work & Study": ws(
        "school class lesson study learn teacher student education academic exam test "
        "homework project office company business job career meeting email report data "
        "computer software file document account budget customer service professional "
        "market research training skill practice vocabulary pronunciation grammar "
        "language write writing read reading book college university course certificate "
        "qualification work worker manager office industry article note paper"
    ),
    "People & Feelings": ws(
        "people person man woman boy girl child children adult baby family parent mother "
        "father brother sister husband wife partner friend friendship community "
        "relationship love like hate happy sad angry afraid fear worry proud confidence "
        "confident jealous excited boring bored brave kind polite rude honest lazy "
        "friendly helpful careful emotional feeling feelings smile cry laugh celebrate "
        "birthday marry marriage team boss leader staff employee colleague neighbor hero "
        "victim citizen audience visitor guest host crowd"
    ),
    "Travel & Places": ws(
        "travel trip journey holiday vacation tour tourist airport airplane plane flight "
        "train bus taxi car bicycle bike motorcycle ship boat ticket passport visa hotel "
        "hostel luggage map station stop route road street bridge corner north south "
        "east west city town village country area region place destination entrance exit "
        "upstairs downstairs abroad local foreign arrive departure depart direction "
        "traffic park parking beach river sea ocean island mountain hill forest camp "
        "guide location port square avenue capital"
    ),
    "Home & Food": ws(
        "home house flat apartment room bedroom bathroom kitchen dining living garden "
        "yard floor wall window door table chair desk sofa bed pillow blanket cup bottle "
        "plate bowl spoon fork knife pan pot dish meal breakfast lunch dinner snack "
        "bread rice cake coffee tea water milk juice fruit vegetable meat fish egg salt "
        "sugar cook cooking clean shower bath clothes clothing shirt shoe shoes sock hat "
        "coat jacket bag box key lamp light fridge freezer oven mirror picture clock toy "
        "wash drawer shelf pocket"
    ),
    "Nature & Health": ws(
        "health healthy body head face eye ear nose mouth neck arm hand finger leg foot "
        "feet heart brain blood skin hair tooth teeth stomach back chest pain sick "
        "illness disease fever cold flu doctor nurse hospital medicine medical treatment "
        "exercise sport sports walk run sleep rest breathe energy strong weak balance "
        "accident danger safe safety risk animal bird dog cat horse cow sheep pig fish "
        "tree plant flower grass leaf weather rain snow wind sun moon star sky fire air "
        "earth environment nature natural climate season spring summer autumn winter "
        "temperature hot warm cool virus injury wound chemical farming"
    ),
    "Actions & Thinking": ws(
        "action act active activity do make take get give put keep let help use change "
        "choose decide plan build create develop improve solve find look think know "
        "understand remember forget check follow try need want hope seem appear become "
        "allow avoid continue stop add remove move turn buy sell pay call ask answer "
        "speak tell show hear listen watch send receive meet win lose discover effect "
        "control connect repeat review explain discuss achieve aim adapt arrange attack "
        "beat break bring carry catch compare consider cut deal defend draw drive drop "
        "encourage ensure enter establish face fail fill fix gain handle hold imagine "
        "influence judge jump kill lead leave manage mark measure miss notice offer pass "
        "pick prepare prevent produce promise protect prove pull push raise reach reduce "
        "refuse relate remain replace respect return reveal save search select set share "
        "shoot shut sign sing sit stand stick strike survive teach touch treat trust "
        "visit vote wait warn wear"
    ),
    "Society & Media": ws(
        "media news newspaper magazine article story stories movie film music song radio "
        "television tv video camera photo photograph internet online website app "
        "application mobile social society culture cultural art artist design theatre "
        "drama dance law legal police government public private national international "
        "history historical science scientific technology technical politics political "
        "war peace religion religious church festival event communication message text "
        "post blog advertisement marketing brand fashion style color colour museum "
        "library literature journalist editor screen channel network press phone tablet "
        "democracy economy economic trade tradition modern"
    ),
}


def clean_word(raw):
    return re.sub(r"[^\w\s.'-]", "", re.sub(r"\s+[12]$", "", raw)).strip()


def load_seed_categories():
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
    thai_pack = json.loads(
        subprocess.check_output(
            ["node", "-e", node_script],
            cwd=str(APP_ROOT.parent),
            text=True,
            encoding="utf8"
        )
    )
    return {
        key.lower(): row[4]
        for key, row in thai_pack.items()
        if len(row) >= 5 and row[4] in GENERAL_CATEGORIES
    }


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


def score_word(word, seed_categories):
    raw = word.lower()
    tokens = re.split(r"[\s-]+", raw)
    scores = Counter()
    reasons = []

    if raw in seed_categories:
        scores[seed_categories[raw]] += 50
        reasons.append("seed")

    if raw in STARTER_EXACT:
        scores["Starter Everyday"] += 40
        reasons.append("starter_exact")

    for category, keyword_set in KEYWORDS.items():
        if raw in keyword_set:
            scores[category] += 14
            reasons.append(f"keyword:{category}")
        for token in tokens:
            if token in keyword_set:
                scores[category] += 6
                reasons.append(f"token:{category}")

    if len(tokens) > 1 and tokens[0] in COMMON_ACTION_HEADS:
        scores["Actions & Thinking"] += 8
        reasons.append("phrasal_action")

    if any(token in COMMON_ACTION_HEADS for token in tokens):
        scores["Actions & Thinking"] += 4
        reasons.append("action_head")

    if any(token.endswith(("tion", "sion", "ment", "ness", "ity", "ism")) for token in tokens):
        scores["Work & Study"] += 2
        scores["Society & Media"] += 2
        reasons.append("abstract_noun")

    if any(token.endswith(("er", "or", "ist", "ian")) for token in tokens):
        scores["People & Feelings"] += 2
        scores["Work & Study"] += 1
        reasons.append("person_suffix")

    return scores, reasons


def pick_rule_assignment(word, scores, reasons, seed_categories):
    raw = word.lower()
    if raw in seed_categories:
        return seed_categories[raw], "seed"

    if raw in STARTER_EXACT:
        return "Starter Everyday", "starter_exact"

    if not scores:
        return None, ""

    best = max(scores.values())
    tied = [category for category in GENERAL_CATEGORIES if scores[category] == best]

    if best >= 14 and len(tied) == 1:
        return tied[0], "rule"

    if len(word.split()) > 1 and word.split()[0].lower() in COMMON_ACTION_HEADS and best >= 8:
        return "Actions & Thinking", "phrasal_action"

    if zipf_frequency(raw, "en") >= 6.0 and best < 12:
        return "Starter Everyday", "high_freq_starter"

    return None, ""


def zero_shot_assign(words, seed_categories, limit=600):
    sorted_words = sorted(words, key=lambda value: (-zipf_frequency(value.lower(), "en"), value.lower()))
    model_words = sorted_words[:limit]
    fallback_words = sorted_words[limit:]

    classifier = pipeline("zero-shot-classification", model="typeform/distilbert-base-uncased-mnli")
    label_values = list(LABEL_DESCRIPTIONS.values())
    label_lookup = {value: key for key, value in LABEL_DESCRIPTIONS.items()}

    resolved = {}
    source_map = {}

    for start in range(0, len(model_words), 40):
        batch = model_words[start:start + 40]
        sequences = [f"This learner English word or phrase is: {word}." for word in batch]
        results = classifier(
            sequences,
            label_values,
            multi_label=False,
            batch_size=8,
            hypothesis_template="This item belongs to the topic of {}."
        )
        if isinstance(results, dict):
            results = [results]

        for word, row in zip(batch, results):
            label = label_lookup[row["labels"][0]]
            scores, _ = score_word(word, seed_categories)
            scores[label] += 8
            lower = word.lower()
            max_rule_score = max(scores.values()) if scores else 0
            if zipf_frequency(lower, "en") >= 6.5 and scores["Starter Everyday"] >= scores[label]:
                resolved[word] = "Starter Everyday"
                source_map[word] = "high_freq_starter"
            elif zipf_frequency(lower, "en") >= 5.8 and max_rule_score < 10:
                if word.split()[0].lower() in COMMON_ACTION_HEADS:
                    resolved[word] = "Actions & Thinking"
                    source_map[word] = "high_freq_action"
                else:
                    resolved[word] = "Starter Everyday"
                    source_map[word] = "high_freq_starter"
            else:
                resolved[word] = max(GENERAL_CATEGORIES, key=lambda category: (scores[category], -GENERAL_CATEGORIES.index(category)))
                source_map[word] = "zero_shot"

    for word in fallback_words:
        scores, _ = score_word(word, seed_categories)
        lower = word.lower()
        if zipf_frequency(lower, "en") >= 5.8:
            scores["Starter Everyday"] += 2
        max_rule_score = max(scores.values()) if scores else 0
        if not scores:
            resolved[word] = "Starter Everyday"
            source_map[word] = "fallback_starter"
        elif zipf_frequency(lower, "en") >= 5.6 and max_rule_score < 10:
            if word.split()[0].lower() in COMMON_ACTION_HEADS:
                resolved[word] = "Actions & Thinking"
                source_map[word] = "fallback_action"
            else:
                resolved[word] = "Starter Everyday"
                source_map[word] = "fallback_starter"
        else:
            resolved[word] = max(GENERAL_CATEGORIES, key=lambda category: (scores[category], -GENERAL_CATEGORIES.index(category)))
            source_map[word] = "fallback_rule"

    return resolved, source_map


def build_metadata():
    seed_categories = load_seed_categories()
    words = load_oxford_words()

    assignments = {}
    source_map = {}
    unresolved = []

    for word in words:
        scores, reasons = score_word(word, seed_categories)
        category, source = pick_rule_assignment(word, scores, reasons, seed_categories)
        if category:
            assignments[word] = category
            source_map[word] = source
        else:
            unresolved.append(word)

    if unresolved:
        extra_assignments, extra_sources = zero_shot_assign(unresolved, seed_categories)
        assignments.update(extra_assignments)
        source_map.update(extra_sources)

    for word in words:
        source = source_map[word]
        if source not in {"zero_shot", "fallback_rule"}:
            continue
        lower = word.lower()
        scores, _ = score_word(word, seed_categories)
        assigned_category = assignments[word]
        assigned_score = scores[assigned_category]
        if zipf_frequency(lower, "en") < 5.5 or assigned_score >= 10:
            continue
        if word.split()[0].lower() in COMMON_ACTION_HEADS:
            assignments[word] = "Actions & Thinking"
            source_map[word] = "postprocess_action"
        else:
            assignments[word] = "Starter Everyday"
            source_map[word] = "postprocess_starter"

    by_category = {category: [] for category in GENERAL_CATEGORIES}
    entries = {}

    for word in words:
        lower = word.lower()
        category = assignments[word]
        zipf = round(zipf_frequency(lower, "en"), 4)
        entry = {
            "word": word,
            "category": category,
            "zipf": zipf,
            "source": source_map[word]
        }
        entries[lower] = entry
        by_category[category].append(entry)

    for category in GENERAL_CATEGORIES:
        ranked = sorted(by_category[category], key=lambda item: (-item["zipf"], item["word"].lower()))
        for index, entry in enumerate(ranked, start=1):
            entries[entry["word"].lower()]["categoryRank"] = index

    category_counts = {category: len(by_category[category]) for category in GENERAL_CATEGORIES}
    source_counts = dict(Counter(source_map.values()))

    payload = {
        "version": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceWordList": OXFORD_TXT.name,
        "frequencySource": "wordfreq zipf_frequency",
        "classifierModel": "typeform/distilbert-base-uncased-mnli",
        "totalEntries": len(words),
        "categoryCounts": category_counts,
        "sourceCounts": source_counts,
        "entries": entries
    }
    return payload


def main():
    payload = build_metadata()
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({
        "output": str(OUTPUT),
        "totalEntries": payload["totalEntries"],
        "categoryCounts": payload["categoryCounts"],
        "sourceCounts": payload["sourceCounts"]
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
