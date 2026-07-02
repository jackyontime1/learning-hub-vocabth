#!/usr/bin/env node
import vm from "node:vm";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const SCRIPT_PATH = fileURLToPath(import.meta.url);
const SCRIPT_DIR = path.dirname(SCRIPT_PATH);
const APP_ROOT = path.resolve(SCRIPT_DIR, "..");
const APP_JS = path.join(APP_ROOT, "app.js");
const OXFORD_WORDS = path.join(APP_ROOT, "oxford3000.txt");
const OXFORD_METADATA = path.join(APP_ROOT, "oxford-metadata.json");
const OXFORD_TRANSLATIONS = path.join(APP_ROOT, "oxford-translations.json");
const DEFAULT_MANIFEST = path.join(APP_ROOT, "audio", "manifest.json");
const DEFAULT_JOBS = path.join(APP_ROOT, "audio", "jobs", "oxford-daily-batch.json");
const DEFAULT_API_KEY = path.resolve(APP_ROOT, "..", ".secrets", "google-tts-api-key.txt");
const BACKUPS_ROOT = path.resolve(APP_ROOT, "..", "backups");
const DEFAULT_AUTOMATION_MEMORY = path.join(
  process.env.CODEX_HOME || (process.env.USERPROFILE ? path.join(process.env.USERPROFILE, ".codex") : ""),
  "automations",
  "oxford-mp3-daily-batch",
  "memory.md"
);
const DEFAULT_MONTHLY_CAP = 900000;
const DEFAULT_RUN_CAP = 16000;
const DEFAULT_NEW_WORD_CAP = 20;
const DEFAULT_LESSON_CAP = 2;
const DEFAULT_MP3_FILE_CAP = 70;
const DAY_SIZE = 10;
const REVIEW_CAP = 50;
const AUDIO_PROFILE = "english-balanced-v2";
const PROFILE_SETTINGS = {
  englishVolumeGainDb: 5,
  englishWordSpeakingRate: 0.98,
  englishExampleSpeakingRate: 0.88
};
const GENERAL_CATEGORY_ORDER = [
  "Starter Everyday",
  "Work & Study",
  "People & Feelings",
  "Travel & Places",
  "Home & Food",
  "Nature & Health",
  "Actions & Thinking",
  "Society & Media"
];
const PROTECTED_CATEGORIES = new Set([
  "Job Interview Q&A",
  "Construction Core",
  "Construction Tools & Equipment"
]);

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const raw = argv[i];
    if (!raw.startsWith("--")) continue;
    const key = raw.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      args[key] = true;
    } else {
      args[key] = next;
      i += 1;
    }
  }
  return args;
}

function readJson(filePath, fallback = null) {
  if (!existsSync(filePath)) return fallback;
  return JSON.parse(readFileSync(filePath, "utf8"));
}

function writeJson(filePath, value) {
  mkdirSync(path.dirname(filePath), { recursive: true });
  writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function pad2(value) {
  return String(value).padStart(2, "0");
}

function localTimestamp(date = new Date()) {
  return [
    date.getFullYear(),
    pad2(date.getMonth() + 1),
    pad2(date.getDate())
  ].join("") + `-${pad2(date.getHours())}${pad2(date.getMinutes())}${pad2(date.getSeconds())}`;
}

function monthBucket(date = new Date()) {
  return date.toISOString().slice(0, 7);
}

function cleanText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function cleanWord(value) {
  return cleanText(value).replace(/\s+/g, " ");
}

function escapeSsml(value) {
  return cleanText(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function spellForSpeech(word) {
  const letters = cleanText(word).replace(/[^a-z]/gi, "").split("");
  return letters.length ? `${letters.join(". ")}.` : cleanText(word);
}

function ssml(segment) {
  const pause = Number(segment.pauseMs || 0);
  const breakTag = pause > 0 ? `<break time="${Math.min(pause, 10000)}ms"/>` : "";
  return `<speak>${escapeSsml(segment.text)}${breakTag}</speak>`;
}

function providerName() {
  return "google-cloud-tts";
}

function voiceConfig(lang) {
  if (lang === "en") {
    return {
      languageCode: "en-US",
      name: "en-US-Chirp3-HD-Puck",
      speakingRate: PROFILE_SETTINGS.englishWordSpeakingRate,
      pitch: 0
    };
  }
  return {
    languageCode: "th-TH",
    name: "th-TH-Chirp3-HD-Puck",
    speakingRate: 1.08,
    pitch: 0
  };
}

function applyAudioProfile(segments) {
  return segments.map(segment => {
    if (segment.lang !== "en") return segment;
    return {
      ...segment,
      speakingRate: segment.role === "example" ? PROFILE_SETTINGS.englishExampleSpeakingRate : PROFILE_SETTINGS.englishWordSpeakingRate,
      volumeGainDb: PROFILE_SETTINGS.englishVolumeGainDb
    };
  });
}

function buildPromptAnswerSegments(item, includeSpelling, includeExample) {
  const segments = [
    { lang: "th", text: "คำว่า", pauseMs: 50 },
    { lang: "en", text: item.word, pauseMs: 50 },
    { lang: "th", text: "แปลว่าอะไร", pauseMs: 3000 },
    { lang: "en", text: item.word, pauseMs: 120 }
  ];
  if (includeSpelling) {
    segments.push({ lang: "en", text: spellForSpeech(item.word), pauseMs: 120 });
  }
  segments.push({ lang: "en", text: item.word, pauseMs: 140 });
  segments.push({ lang: "th", text: item.meaning, pauseMs: includeExample ? 220 : 500 });
  if (includeExample) {
    segments.push({ lang: "en", text: item.example, pauseMs: 150, role: "example" });
    segments.push({ lang: "th", text: item.exampleTh, pauseMs: 500 });
  }
  return applyAudioProfile(segments);
}

function buildItemSegments(item, includeSpelling) {
  if (item.mode === "review") {
    return applyAudioProfile([
      { lang: "th", text: `คำว่า ${item.meaning} ภาษาอังกฤษคืออะไร`, pauseMs: 3000 },
      { lang: "en", text: item.word, pauseMs: 140 },
      { lang: "th", text: item.meaning, pauseMs: 500 }
    ]).map(segment => ({ ...segment, text: cleanText(segment.text) })).filter(segment => segment.text);
  }
  const includeExample = item.mode === "full" && item.hasCuratedExample && item.example && item.exampleTh;
  return buildPromptAnswerSegments(item, includeSpelling, includeExample)
    .map(segment => ({ ...segment, text: cleanText(segment.text) }))
    .filter(segment => segment.text);
}

function estimateChars(segments) {
  return segments.reduce((sum, segment) => sum + ssml(segment).length, 0);
}

async function synthesizeGoogle(segment, outputPath, apiKey) {
  if (!apiKey) {
    throw new Error("Missing Google TTS API key. Use --api-key-file.");
  }

  const voice = voiceConfig(segment.lang);
  const audioConfig = {
    audioEncoding: "MP3",
    speakingRate: Number(segment.speakingRate || voice.speakingRate)
  };
  if (Number.isFinite(Number(segment.volumeGainDb))) {
    audioConfig.volumeGainDb = Number(segment.volumeGainDb);
  }

  const body = {
    input: { ssml: ssml(segment) },
    voice: {
      languageCode: voice.languageCode,
      name: voice.name
    },
    audioConfig
  };

  const res = await fetch(`https://texttospeech.googleapis.com/v1/text:synthesize?key=${apiKey}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Google TTS failed (${res.status}): ${detail.slice(0, 400)}`);
  }

  const payload = await res.json();
  if (!payload.audioContent) throw new Error("Google TTS response has no audioContent");
  await writeFile(outputPath, Buffer.from(payload.audioContent, "base64"));
}

function findFfmpeg(explicitPath) {
  const candidates = [
    explicitPath,
    process.env.FFMPEG_PATH,
    "ffmpeg"
  ].filter(Boolean);

  for (const candidate of candidates) {
    const result = spawnSync(candidate, ["-version"], { encoding: "utf8", windowsHide: true });
    if (result.status === 0) return candidate;
  }
  return "";
}

function concatListLine(filePath) {
  return `file '${filePath.replace(/\\/g, "/").replace(/'/g, "'\\''")}'`;
}

function powershellLiteral(value) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

async function concatMp3(parts, outputPath, ffmpegPath) {
  mkdirSync(path.dirname(outputPath), { recursive: true });
  if (ffmpegPath) {
    const listPath = path.join(path.dirname(outputPath), ".concat-list.txt");
    writeFileSync(listPath, parts.map(concatListLine).join("\n"), "utf8");
    const result = spawnSync(
      ffmpegPath,
      ["-y", "-f", "concat", "-safe", "0", "-i", listPath, "-codec:a", "libmp3lame", "-b:a", "128k", outputPath],
      { encoding: "utf8", windowsHide: true }
    );
    rmSync(listPath, { force: true });
    if (result.status !== 0) {
      throw new Error(`ffmpeg concat failed: ${(result.stderr || result.stdout || "").slice(0, 600)}`);
    }
    return;
  }

  const buffers = parts.map(part => readFileSync(part));
  writeFileSync(outputPath, Buffer.concat(buffers));
  console.warn("No ffmpeg found. Wrote a binary MP3 concat fallback; install ffmpeg for cleaner output.");
}

function verifyMp3(filePath, ffmpegPath) {
  const result = spawnSync(
    ffmpegPath,
    ["-v", "error", "-i", filePath, "-f", "null", "-"],
    { encoding: "utf8", windowsHide: true }
  );
  if (result.status !== 0) {
    throw new Error(`ffmpeg decode failed for ${filePath}: ${(result.stderr || result.stdout || "").slice(0, 600)}`);
  }
}

function verifyGeneratedMp3s(filePaths, ffmpegPath) {
  for (const filePath of filePaths) {
    verifyMp3(filePath, ffmpegPath);
  }
}

function createBackup(selection, manifestPath, jobsPath) {
  mkdirSync(BACKUPS_ROOT, { recursive: true });
  const backupPath = path.join(BACKUPS_ROOT, `before-oxford-daily-batch-${localTimestamp()}.zip`);
  const profileRoots = [...new Set(
    selection.selected.map(lesson =>
      path.join(APP_ROOT, "audio", "words", lesson.categorySlug, "profiles", safeFileStem(lesson.audioProfile))
    )
  )].filter(existsSync);

  const includePaths = [
    manifestPath,
    jobsPath,
    SCRIPT_PATH,
    ...profileRoots
  ].filter(existsSync);

  const command = `Compress-Archive -LiteralPath @(${includePaths.map(powershellLiteral).join(", ")}) -DestinationPath ${powershellLiteral(backupPath)} -CompressionLevel Optimal -Force`;
  const result = spawnSync(
    "powershell.exe",
    ["-NoProfile", "-Command", command],
    { encoding: "utf8", windowsHide: true }
  );
  if (result.status !== 0) {
    throw new Error(`Backup creation failed: ${(result.stderr || result.stdout || "").slice(0, 600)}`);
  }
  return backupPath;
}

function extractObjectLiteral(source, declaration) {
  const declarationIndex = source.indexOf(declaration);
  if (declarationIndex < 0) throw new Error(`Missing declaration: ${declaration}`);
  const braceStart = source.indexOf("{", declarationIndex);
  if (braceStart < 0) throw new Error(`Missing object start: ${declaration}`);

  let depth = 0;
  let inString = false;
  let stringChar = "";
  let escaped = false;

  for (let index = braceStart; index < source.length; index += 1) {
    const char = source[index];
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === stringChar) {
        inString = false;
        stringChar = "";
      }
      continue;
    }

    if (char === "\"" || char === "'" || char === "`") {
      inString = true;
      stringChar = char;
      continue;
    }
    if (char === "{") depth += 1;
    if (char === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(braceStart, index + 1);
    }
  }

  throw new Error(`Unclosed object literal for ${declaration}`);
}

function loadThaiPack() {
  const source = readFileSync(APP_JS, "utf8");
  const objectLiteral = extractObjectLiteral(source, "const thaiPack =");
  return vm.runInNewContext(`(${objectLiteral})`);
}

function slugifyCategory(category) {
  return category
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/q\s*and\s*a/g, "qanda")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function safeFileStem(value) {
  return cleanText(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "word";
}

function itemOutputPath(lesson, item, includeSpelling) {
  const profile = safeFileStem(lesson.audioProfile);
  if (item.mode === "review") {
    const fileName = `${safeFileStem(item.reviewFileStem || item.word)}.mp3`;
    const rel = `audio/words/${lesson.categorySlug}/profiles/${profile}/review/${fileName}`;
    return { rel, abs: path.join(APP_ROOT, rel) };
  }
  const day = `day-${String(lesson.day).padStart(3, "0")}`;
  const fileName = `${String(item.order + 1).padStart(3, "0")}-${safeFileStem(item.word)}${includeSpelling ? "" : "-no-spelling"}.mp3`;
  const rel = `audio/words/${lesson.categorySlug}/profiles/${profile}/${day}/${fileName}`;
  return { rel, abs: path.join(APP_ROOT, rel) };
}

function loadManifest(filePath, cap, bucket) {
  const manifest = readJson(filePath, null) || {};
  manifest.version = 2;
  manifest.generatedBy = "oxford-tts-batch";
  manifest.monthCapChars = cap;
  manifest.monthBucket = bucket;
  manifest.lessons = manifest.lessons || {};
  manifest.usage = Array.isArray(manifest.usage) ? manifest.usage : [];
  return manifest;
}

function usedCharsForMonth(manifest, bucket) {
  return manifest.usage
    .filter(row => row.monthBucket === bucket)
    .reduce((sum, row) => sum + Number(row.usedChars || row.estimatedChars || 0), 0);
}

function fileReady(filePath) {
  return existsSync(filePath);
}

function buildOxfordEntries() {
  const thaiPack = loadThaiPack();
  const metadata = readJson(OXFORD_METADATA);
  const translations = readJson(OXFORD_TRANSLATIONS);
  const rawWords = readFileSync(OXFORD_WORDS, "utf8")
    .split(/\r?\n/)
    .map(cleanWord)
    .filter(Boolean);
  const words = [...new Map(rawWords.map(word => [word.toLowerCase(), word])).values()];

  const categoryBuckets = new Map(GENERAL_CATEGORY_ORDER.map(category => [category, []]));

  for (const word of words) {
    const lower = cleanWord(word.toLowerCase());
    const meta = metadata?.entries?.[lower];
    const translation = translations?.entries?.[lower];
    const packed = thaiPack?.[lower];
    const category = meta?.category || packed?.[4] || "";

    if (!categoryBuckets.has(category)) continue;
    if (PROTECTED_CATEGORIES.has(category)) continue;
    if (!translation?.meaning && !packed?.[1]) continue;

    const example = packed?.[2] || "";
    const exampleTh = translation?.exampleTh || packed?.[3] || "";
    const hasCuratedExample = Boolean(example && exampleTh && (translation?.hasCuratedExample || packed?.[2]));

    categoryBuckets.get(category).push({
      word: cleanWord(word),
      meaning: translation?.meaning || packed?.[1] || "",
      example,
      exampleTh,
      hasCuratedExample,
      category,
      zipf: Number(meta?.zipf || 0),
      categoryRank: Number(meta?.categoryRank || Number.MAX_SAFE_INTEGER)
    });
  }

  for (const entries of categoryBuckets.values()) {
    entries.sort((a, b) => (a.categoryRank - b.categoryRank) || b.zipf - a.zipf || a.word.localeCompare(b.word));
    const stemCounts = new Map();
    for (const entry of entries) {
      const stem = safeFileStem(entry.word);
      stemCounts.set(stem, (stemCounts.get(stem) || 0) + 1);
    }
    entries.forEach((entry, index) => {
      const stem = safeFileStem(entry.word);
      const disambiguator = Number.isFinite(entry.categoryRank) ? entry.categoryRank : index + 1;
      entry.reviewFileStem = stemCounts.get(stem) > 1 ? `${stem}-r${disambiguator}` : stem;
    });
  }

  return categoryBuckets;
}

function toLessonItem(entry, mode, order) {
  return {
    word: entry.word,
    meaning: entry.meaning,
    example: entry.example,
    exampleTh: entry.exampleTh,
    hasCuratedExample: entry.hasCuratedExample,
    zipf: entry.zipf,
    categoryRank: entry.categoryRank,
    reviewFileStem: entry.reviewFileStem,
    mode,
    order
  };
}

function buildLessons(categoryBuckets) {
  const lessons = [];
  const globalWords = [];

  for (const category of GENERAL_CATEGORY_ORDER) {
    const entries = categoryBuckets.get(category) || [];
    const categorySlug = slugifyCategory(category);
    const totalDays = Math.ceil(entries.length / DAY_SIZE);

    for (let day = 1; day <= totalDays; day += 1) {
      const todayStart = (day - 1) * DAY_SIZE;
      const todayEnd = Math.min(todayStart + DAY_SIZE, entries.length);
      const today = entries.slice(todayStart, todayEnd);
      const reviewLimit = Math.max(0, REVIEW_CAP - today.length);
      const reviewStart = Math.max(0, todayStart - reviewLimit);
      const previous = entries.slice(reviewStart, todayStart);
      const lessonItems = [];

      for (const row of previous) {
        lessonItems.push(toLessonItem(row, "review", lessonItems.length));
      }
      for (const row of today) {
        const mode = row.hasCuratedExample ? "full" : "word-meaning";
        lessonItems.push(toLessonItem(row, mode, lessonItems.length));
      }

      const lesson = {
        id: `${categorySlug}__day-${String(day).padStart(3, "0")}`,
        category,
        categorySlug,
        day,
        audioProfile: AUDIO_PROFILE,
        items: lessonItems
      };

      lessons.push(lesson);

      for (const item of lessonItems.filter(row => row.mode !== "review")) {
        globalWords.push({
          lessonId: lesson.id,
          category,
          day,
          word: item.word,
          zipf: item.zipf,
          categoryRank: item.categoryRank,
          order: item.order
        });
      }
    }
  }

  globalWords.sort((a, b) => {
    const zipfDiff = b.zipf - a.zipf;
    if (zipfDiff) return zipfDiff;
    const categoryDiff = GENERAL_CATEGORY_ORDER.indexOf(a.category) - GENERAL_CATEGORY_ORDER.indexOf(b.category);
    if (categoryDiff) return categoryDiff;
    const rankDiff = a.categoryRank - b.categoryRank;
    if (rankDiff) return rankDiff;
    return a.word.localeCompare(b.word);
  });

  return { lessons, globalWords };
}

function summarizeLesson(lesson) {
  const fullItems = lesson.items.filter(item => item.mode !== "review");
  return {
    ...lesson,
    fullItems
  };
}

function isWordComplete(lesson, item) {
  if (item.mode === "review") return fileReady(itemOutputPath(lesson, item, true).abs);
  const withSpelling = itemOutputPath(lesson, item, true).abs;
  const withoutSpelling = itemOutputPath(lesson, item, false).abs;
  return fileReady(withSpelling) && fileReady(withoutSpelling);
}

function estimateLessonGeneration(lesson) {
  let withSpellingChars = 0;
  let withoutSpellingChars = 0;
  let withSpellingFiles = 0;
  let withoutSpellingFiles = 0;
  let missingFullWords = 0;

  for (const item of lesson.items) {
    const reviewOrWithPath = itemOutputPath(lesson, item, true);
    const withoutPath = item.mode === "review" ? reviewOrWithPath : itemOutputPath(lesson, item, false);
    const needsWithSpelling = !fileReady(reviewOrWithPath.abs);
    const needsWithoutSpelling = item.mode === "review" ? false : !fileReady(withoutPath.abs);

    if (needsWithSpelling) {
      withSpellingChars += estimateChars(buildItemSegments(item, true));
      withSpellingFiles += 1;
    }
    if (needsWithoutSpelling) {
      withoutSpellingChars += estimateChars(buildItemSegments(item, false));
      withoutSpellingFiles += 1;
    }
    if (item.mode !== "review" && (!fileReady(reviewOrWithPath.abs) || !fileReady(withoutPath.abs))) {
      missingFullWords += 1;
    }
  }

  return {
    withSpellingChars,
    withoutSpellingChars,
    totalChars: withSpellingChars + withoutSpellingChars,
    withSpellingFiles,
    withoutSpellingFiles,
    totalFiles: withSpellingFiles + withoutSpellingFiles,
    missingFullWords
  };
}

function selectLessons({ lessons, globalWords, maxLessons, maxNewWords, maxRunChars, maxMp3Files }) {
  const lessonById = new Map(lessons.map(lesson => [lesson.id, summarizeLesson(lesson)]));
  const selectedLessonIds = new Set();
  const selected = [];
  let selectedNewWords = 0;
  let selectedChars = 0;
  let selectedFiles = 0;

  const completeWordKeys = new Set();
  for (const lesson of lessonById.values()) {
    for (const item of lesson.fullItems) {
      if (isWordComplete(lesson, item)) {
        completeWordKeys.add(`${lesson.id}::${item.word.toLowerCase()}`);
      }
    }
  }

  for (const word of globalWords) {
    const wordKey = `${word.lessonId}::${word.word.toLowerCase()}`;
    if (completeWordKeys.has(wordKey)) continue;

    const lesson = lessonById.get(word.lessonId);
    if (!lesson) continue;
    if (selectedLessonIds.has(lesson.id)) continue;
    if (selectedLessonIds.size >= maxLessons) break;

    const estimate = estimateLessonGeneration(lesson);
    if (!estimate.missingFullWords) continue;
    if (selectedNewWords && selectedNewWords + estimate.missingFullWords > maxNewWords) break;
    if (selectedChars && selectedChars + estimate.totalChars > maxRunChars) break;
    if (selectedFiles && selectedFiles + estimate.totalFiles > maxMp3Files) break;
    if (!selectedLessonIds.size && maxLessons < 1) {
      throw new Error(`The Oxford run lesson cap must be at least 1; received ${maxLessons}.`);
    }
    if (!selectedNewWords && estimate.missingFullWords > maxNewWords) {
      throw new Error(`The next Oxford lesson ${lesson.id} needs ${estimate.missingFullWords} new words, above the run cap ${maxNewWords}.`);
    }
    if (!selectedChars && estimate.totalChars > maxRunChars) {
      throw new Error(`The next Oxford lesson ${lesson.id} needs ${estimate.totalChars} chars, above the run cap ${maxRunChars}.`);
    }
    if (!selectedFiles && estimate.totalFiles > maxMp3Files) {
      throw new Error(`The next Oxford lesson ${lesson.id} needs ${estimate.totalFiles} MP3 files, above the run cap ${maxMp3Files}.`);
    }

    selectedLessonIds.add(lesson.id);
    selectedNewWords += estimate.missingFullWords;
    selectedChars += estimate.totalChars;
    selectedFiles += estimate.totalFiles;
    selected.push({
      ...lesson,
      estimate
    });
  }

  const pendingAfterSelection = globalWords.find(word => {
    const wordKey = `${word.lessonId}::${word.word.toLowerCase()}`;
    if (completeWordKeys.has(wordKey)) return false;
    return !selectedLessonIds.has(word.lessonId);
  }) || null;

  return {
    selected,
    newWords: selectedNewWords,
    estimatedChars: selectedChars,
    mp3Files: selectedFiles,
    nextWord: pendingAfterSelection ? {
      word: pendingAfterSelection.word,
      category: pendingAfterSelection.category,
      day: pendingAfterSelection.day
    } : null
  };
}

function buildJobsPayload(selection, bucket, maxLessons, maxNewWords, maxRunChars, maxMp3Files, safetyReport) {
  return {
    version: 1,
    app: "VocabTH / Oxford Audio Vocabulary",
    scope: "oxford-daily-batch",
    generatedAt: new Date().toISOString(),
    monthBucket: bucket,
    limits: {
      maxLessons,
      maxNewWords,
      maxRunChars,
      maxMp3Files
    },
    summary: {
      selectedLessons: selection.selected.length,
      newWords: selection.newWords,
      mp3Files: selection.mp3Files,
      estimatedChars: selection.estimatedChars,
      nextWord: selection.nextWord,
      safety: safetyReport
    },
    lessons: selection.selected.map(lesson => ({
      id: lesson.id,
      category: lesson.category,
      categorySlug: lesson.categorySlug,
      day: lesson.day,
      audioProfile: lesson.audioProfile,
      estimate: lesson.estimate,
      items: lesson.items
    }))
  };
}

function toPosixPath(value) {
  return String(value).replace(/\\/g, "/");
}

function manifestRefToAbs(ref) {
  return path.join(APP_ROOT, String(ref).replace(/\//g, path.sep));
}

function collectManifestMp3Refs(manifest) {
  const refs = [];
  for (const lesson of Object.values(manifest.lessons || {})) {
    for (const item of lesson.items || []) {
      for (const field of ["fileWithSpelling", "fileWithoutSpelling", "file", "src"]) {
        if (item[field] && String(item[field]).endsWith(".mp3")) refs.push(String(item[field]));
      }
    }
  }
  return refs;
}

function validateManifestReferences(manifest) {
  const refs = collectManifestMp3Refs(manifest);
  const missing = [...new Set(refs)].filter(ref => !fileReady(manifestRefToAbs(ref)));
  if (missing.length) {
    throw new Error(`Manifest has ${missing.length} missing MP3 reference(s). First missing reference: ${missing[0]}`);
  }
  return {
    rawMp3Refs: refs.length,
    uniqueMp3Refs: new Set(refs).size,
    missingMp3Refs: 0
  };
}

function validateCompletedOxfordLessonsInManifest(lessons, manifest) {
  const stale = [];
  for (const lesson of lessons) {
    if (!lesson.fullItems.length) continue;
    const fullItemsComplete = lesson.fullItems.every(item => isWordComplete(lesson, item));
    if (!fullItemsComplete) continue;

    const entry = manifest.lessons?.[lesson.id];
    if (!entry || entry.status !== "generated" || !Array.isArray(entry.items)) {
      stale.push(`${lesson.id}: physical MP3s exist but manifest entry is missing or not generated`);
      continue;
    }

    const manifestItems = new Map(entry.items.map(item => [String(item.word || "").toLowerCase(), item]));
    for (const item of lesson.fullItems) {
      const manifestItem = manifestItems.get(item.word.toLowerCase());
      if (!manifestItem?.fileWithSpelling || !manifestItem?.fileWithoutSpelling) {
        stale.push(`${lesson.id}: manifest is missing MP3 fields for ${item.word}`);
        break;
      }
      if (!fileReady(manifestRefToAbs(manifestItem.fileWithSpelling)) || !fileReady(manifestRefToAbs(manifestItem.fileWithoutSpelling))) {
        stale.push(`${lesson.id}: manifest MP3 path does not exist for ${item.word}`);
        break;
      }
    }
  }

  if (stale.length) {
    throw new Error(`Oxford manifest/status appears stale. ${stale.slice(0, 3).join(" | ")}`);
  }
  return { staleCompletedLessons: 0 };
}

function collectSelectionOutputPlans(selection) {
  const plans = [];
  for (const lesson of selection.selected) {
    for (const includeSpelling of [true, false]) {
      const variant = includeSpelling ? "withSpelling" : "withoutSpelling";
      for (const item of lesson.items) {
        if (item.mode === "review" && !includeSpelling) continue;
        const output = itemOutputPath(lesson, item, includeSpelling);
        plans.push({
          lessonId: lesson.id,
          variant,
          word: item.word,
          mode: item.mode,
          rel: output.rel,
          abs: output.abs,
          needsGeneration: !fileReady(output.abs)
        });
      }
    }
  }
  return plans;
}

function validateSelectionSafety(selection, limits) {
  if (selection.selected.length > limits.maxLessons) {
    throw new Error(`Autopilot safety stopped run: ${selection.selected.length} lessons exceeds cap ${limits.maxLessons}.`);
  }
  if (selection.newWords > limits.maxNewWords) {
    throw new Error(`Autopilot safety stopped run: ${selection.newWords} new words exceeds cap ${limits.maxNewWords}.`);
  }
  if (selection.estimatedChars > limits.maxRunChars) {
    throw new Error(`Autopilot safety stopped run: ${selection.estimatedChars} estimated chars exceeds cap ${limits.maxRunChars}.`);
  }

  const plans = collectSelectionOutputPlans(selection);
  const duplicatePaths = [];
  const seen = new Set();
  for (const plan of plans) {
    const key = plan.rel.toLowerCase();
    if (seen.has(key)) duplicatePaths.push(plan.rel);
    seen.add(key);
  }
  if (duplicatePaths.length) {
    throw new Error(`Autopilot safety stopped run: duplicate output path(s): ${duplicatePaths.slice(0, 3).join(", ")}`);
  }

  const missingPlans = plans.filter(plan => plan.needsGeneration);
  if (missingPlans.length > limits.maxMp3Files) {
    throw new Error(`Autopilot safety stopped run: ${missingPlans.length} MP3 files exceeds cap ${limits.maxMp3Files}.`);
  }

  return {
    duplicateOutputPaths: 0,
    overwriteRenameDeleteRisk: 0,
    mp3FilesToGenerate: missingPlans.length,
    existingFilesReused: plans.length - missingPlans.length
  };
}

function assertCleanWorktreeForLiveRun({ jobsPath, dryRun }) {
  const repoRoot = path.resolve(APP_ROOT, "..");
  const result = spawnSync(
    "git",
    ["-C", repoRoot, "status", "--porcelain=v1", "--untracked-files=all"],
    { encoding: "utf8", windowsHide: true }
  );
  if (result.status !== 0) {
    throw new Error(`Unable to inspect git status before Oxford TTS run: ${(result.stderr || result.stdout || "").slice(0, 400)}`);
  }

  const allowedJobPath = toPosixPath(path.relative(repoRoot, jobsPath));
  const dirty = (result.stdout || "")
    .split(/\r?\n/)
    .map(line => line.trimEnd())
    .filter(Boolean)
    .filter(line => toPosixPath(line.slice(3)) !== allowedJobPath);

  if (!dirty.length) {
    return { cleanWorktree: true, ignoredGeneratedJobFile: false };
  }

  const translationConflict = dirty.find(line => line.includes("daily-english-reader/data/cache/translations.json"));
  const prefix = dryRun ? "Autopilot strict dry-run" : "Autopilot live TTS";
  if (translationConflict) {
    throw new Error(`${prefix} stopped: protected translations.json is dirty/conflicted (${translationConflict}).`);
  }
  throw new Error(`${prefix} stopped: git worktree is not clean. First dirty path: ${dirty[0]}`);
}

function validateAutomationMemoryFresh({ memoryPath, manifest, bucket, cap }) {
  if (!memoryPath || !existsSync(memoryPath)) {
    return { automationMemoryChecked: false };
  }
  const text = readFileSync(memoryPath, "utf8");
  const used = usedCharsForMonth(manifest, bucket);
  const usageNeedles = [
    `${used} / ${cap}`,
    `${used}/${cap}`,
    `${used.toLocaleString("en-US")} / ${cap.toLocaleString("en-US")}`,
    `${used.toLocaleString("en-US")}/${cap.toLocaleString("en-US")}`
  ];
  if (!usageNeedles.some(needle => text.includes(needle))) {
    throw new Error(`Autopilot safety stopped run: automation memory appears stale; it does not record current manifest usage ${used}/${cap}.`);
  }
  return {
    automationMemoryChecked: true,
    automationMemoryUsageMatchesManifest: true
  };
}

async function synthesizeSegmentsToFile({ segments, outputPath, apiKey, ffmpegPath, tempDir }) {
  rmSync(tempDir, { recursive: true, force: true });
  mkdirSync(tempDir, { recursive: true });
  const parts = [];
  try {
    for (let index = 0; index < segments.length; index += 1) {
      const segment = segments[index];
      const partPath = path.join(tempDir, `${String(index + 1).padStart(3, "0")}-${segment.lang}.mp3`);
      await synthesizeGoogle(segment, partPath, apiKey);
      parts.push(partPath);
    }
    await concatMp3(parts, outputPath, ffmpegPath);
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

function upsertItemEntry(previous, item, lesson, includeSpelling) {
  const output = itemOutputPath(lesson, item, includeSpelling);
  const base = {
    ...previous,
    word: item.word,
    order: item.order,
    mode: item.mode
  };
  if (item.mode === "review") {
    base.fileWithSpelling = output.rel;
    base.fileWithoutSpelling = output.rel;
    return base;
  }
  if (includeSpelling) {
    base.fileWithSpelling = output.rel;
  } else {
    base.fileWithoutSpelling = output.rel;
  }
  return base;
}

async function generateVariant({ lesson, includeSpelling, apiKey, ffmpegPath, manifest, bucket, cap, dryRun }) {
  const variantName = includeSpelling ? "withSpelling" : "withoutSpelling";
  const prepared = lesson.items.map(item => {
    const output = itemOutputPath(lesson, item, includeSpelling);
    const needsGeneration = item.mode === "review" && !includeSpelling
      ? false
      : !fileReady(output.abs);
    const segments = needsGeneration ? buildItemSegments(item, includeSpelling) : [];
    return {
      item,
      output,
      needsGeneration,
      estimatedChars: needsGeneration ? estimateChars(segments) : 0,
      segments
    };
  });
  const outputPaths = new Set();
  for (const row of prepared) {
    const outputKey = row.output.rel.toLowerCase();
    if (outputPaths.has(outputKey)) {
      throw new Error(`Duplicate output path in ${lesson.id} ${variantName}: ${row.output.rel}`);
    }
    outputPaths.add(outputKey);
  }

  const usedChars = prepared.reduce((sum, row) => sum + row.estimatedChars, 0);
  const fileCount = prepared.filter(row => row.needsGeneration).length;
  const generatedFiles = prepared.filter(row => row.needsGeneration).map(row => row.output.abs);
  if (usedCharsForMonth(manifest, bucket) + usedChars > cap) {
    throw new Error(`Quota guard stopped ${lesson.id} ${variantName}: ${usedCharsForMonth(manifest, bucket) + usedChars}/${cap}`);
  }

  console.log(`${dryRun ? "DRY" : "RUN"} ${lesson.id} ${variantName}: ${usedChars} chars, ${fileCount} files`);
  if (dryRun) return { usedChars, fileCount, generatedFiles };

  for (let index = 0; index < prepared.length; index += 1) {
    const row = prepared[index];
    if (!row.needsGeneration) continue;
    process.stdout.write(`  ${index + 1}/${prepared.length} ${row.item.word} -> ${row.output.rel}\n`);
    await synthesizeSegmentsToFile({
      segments: row.segments,
      outputPath: row.output.abs,
      apiKey,
      ffmpegPath,
      tempDir: path.join(APP_ROOT, "audio", ".tts-parts", lesson.id, variantName, String(index + 1))
    });
  }

  verifyGeneratedMp3s(generatedFiles, ffmpegPath);
  if (generatedFiles.length) {
    console.log(`VERIFIED ${lesson.id} ${variantName}: ${generatedFiles.length} MP3 files`);
  }

  const existingEntry = manifest.lessons[lesson.id] || {};
  const existingItems = Array.isArray(existingEntry.items) ? existingEntry.items : [];
  const nextItems = lesson.items.map(item => {
    const previous = existingItems.find(entry => entry.word.toLowerCase() === item.word.toLowerCase()) || {};
    return upsertItemEntry(previous, item, lesson, includeSpelling);
  });

  manifest.lessons[lesson.id] = {
    ...existingEntry,
    category: lesson.category,
    categorySlug: lesson.categorySlug,
    day: lesson.day,
    audioProfile: lesson.audioProfile,
    provider: providerName(),
    playbackMode: "item-sequence",
    recallPauseMs: 3000,
    itemCount: lesson.items.length,
    monthBucket: bucket,
    voice: {
      en: voiceConfig("en"),
      th: voiceConfig("th")
    },
    profileSettings: PROFILE_SETTINGS,
    variants: {
      ...(existingEntry.variants || {}),
      [variantName]: {
        type: "item-sequence",
        estimatedChars: usedChars,
        fileCount
      }
    },
    items: nextItems,
    status: "generated",
    generatedAt: new Date().toISOString()
  };

  if (usedChars > 0) {
    manifest.usage.push({
      lessonId: lesson.id,
      variant: variantName,
      playbackMode: "item-sequence",
      provider: providerName(),
      monthBucket: bucket,
      usedChars,
      generatedAt: manifest.lessons[lesson.id].generatedAt
    });
  }

  return { usedChars, fileCount, generatedFiles };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const bucket = String(args.month || process.env.TTS_MONTH_BUCKET || monthBucket());
  const cap = Number(args["month-cap"] || process.env.MONTHLY_TTS_CHAR_CAP || DEFAULT_MONTHLY_CAP);
  const maxRunChars = Number(args["max-run-chars"] || DEFAULT_RUN_CAP);
  const maxNewWords = Number(args["max-new-words"] || DEFAULT_NEW_WORD_CAP);
  const maxLessons = Number(args["max-lessons"] || DEFAULT_LESSON_CAP);
  const maxMp3Files = Number(args["max-mp3-files"] || DEFAULT_MP3_FILE_CAP);
  const manifestPath = path.resolve(args.manifest || DEFAULT_MANIFEST);
  const jobsPath = path.resolve(args.jobs || DEFAULT_JOBS);
  const dryRun = Boolean(args["dry-run"]);
  const strictDryRun = Boolean(args["strict-dry-run"] || process.env.OXFORD_STRICT_DRY_RUN);
  const memoryPath = path.resolve(args["memory-file"] || process.env.OXFORD_AUTOMATION_MEMORY || DEFAULT_AUTOMATION_MEMORY);
  const ffmpegPath = findFfmpeg(args.ffmpeg);

  if (!dryRun) {
    assertCleanWorktreeForLiveRun({ jobsPath, dryRun });
  } else if (strictDryRun) {
    assertCleanWorktreeForLiveRun({ jobsPath, dryRun });
  }

  const manifest = loadManifest(manifestPath, cap, bucket);
  const automationMemoryReport = (!dryRun || strictDryRun)
    ? validateAutomationMemoryFresh({ memoryPath, manifest, bucket, cap })
    : { automationMemoryChecked: false };
  const categoryBuckets = buildOxfordEntries();
  const { lessons, globalWords } = buildLessons(categoryBuckets);
  const manifestReferenceReport = validateManifestReferences(manifest);
  const manifestStatusReport = validateCompletedOxfordLessonsInManifest(
    lessons.map(summarizeLesson),
    manifest
  );
  const selection = selectLessons({
    lessons,
    globalWords,
    maxLessons,
    maxNewWords,
    maxRunChars,
    maxMp3Files
  });
  const safetyReport = validateSelectionSafety(selection, {
    maxLessons,
    maxNewWords,
    maxRunChars,
    maxMp3Files
  });
  const jobsPayload = buildJobsPayload(
    selection,
    bucket,
    maxLessons,
    maxNewWords,
    maxRunChars,
    maxMp3Files,
    {
      ...manifestReferenceReport,
      ...manifestStatusReport,
      ...safetyReport,
      ...automationMemoryReport
    }
  );
  writeJson(jobsPath, jobsPayload);

  console.log(`Month cap: ${bucket} ${cap}`);
  console.log(`Autopilot caps: lessons ${maxLessons}, new words ${maxNewWords}, MP3 files ${maxMp3Files}, chars ${maxRunChars}`);
  console.log(`ffmpeg: ${ffmpegPath || "not found; binary concat fallback"}`);
  console.log(`Selected lessons: ${selection.selected.length}`);
  console.log(`Selected new words: ${selection.newWords}`);
  console.log(`Selected MP3 files: ${selection.mp3Files}`);
  console.log(`Estimated run chars: ${selection.estimatedChars}`);
  console.log(`Safety duplicate output paths: ${safetyReport.duplicateOutputPaths}`);
  console.log(`Safety overwrite/rename/delete risk: ${safetyReport.overwriteRenameDeleteRisk}`);
  console.log(`Manifest missing MP3 references: ${manifestReferenceReport.missingMp3Refs}`);
  console.log(`Automation memory checked: ${automationMemoryReport.automationMemoryChecked}`);
  if (selection.nextWord) {
    console.log(`Next word after batch: ${selection.nextWord.word} (${selection.nextWord.category} day ${selection.nextWord.day})`);
  } else {
    console.log("Next word after batch: none");
  }

  if (!selection.selected.length) {
    console.log("No Oxford words need generation.");
    return;
  }

  console.log(`Current month usage: ${usedCharsForMonth(manifest, bucket)}/${cap}`);

  for (const lesson of selection.selected) {
    await generateVariant({ lesson, includeSpelling: true, apiKey: "", ffmpegPath, manifest, bucket, cap, dryRun: true });
    await generateVariant({ lesson, includeSpelling: false, apiKey: "", ffmpegPath, manifest, bucket, cap, dryRun: true });
  }

  if (dryRun) {
    console.log("Dry run complete. Jobs file was updated; manifest was not changed.");
    return;
  }

  if (!ffmpegPath) {
    throw new Error("ffmpeg is required for Oxford batch generation so new MP3 files can be concatenated and verified.");
  }

  const backupPath = createBackup(selection, manifestPath, jobsPath);
  console.log(`Backup: ${backupPath}`);

  const apiKeyFile = path.resolve(args["api-key-file"] || DEFAULT_API_KEY);
  const apiKey = (await readFile(apiKeyFile, "utf8")).trim();
  await mkdir(path.dirname(manifestPath), { recursive: true });

  for (const lesson of selection.selected) {
    await generateVariant({ lesson, includeSpelling: true, apiKey, ffmpegPath, manifest, bucket, cap, dryRun: false });
    writeJson(manifestPath, manifest);
    await generateVariant({ lesson, includeSpelling: false, apiKey, ffmpegPath, manifest, bucket, cap, dryRun: false });
    writeJson(manifestPath, manifest);
  }

  writeJson(manifestPath, manifest);
  console.log(`Wrote ${path.relative(APP_ROOT, manifestPath)}`);
}

main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
