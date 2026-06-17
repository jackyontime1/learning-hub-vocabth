#!/usr/bin/env node
import crypto from "node:crypto";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const APP_ROOT = path.resolve(SCRIPT_DIR, "..");

const DEFAULT_JOB = path.join(APP_ROOT, "audio", "jobs", "job-interview-qanda-day-001.json");
const DEFAULT_MANIFEST = path.join(APP_ROOT, "audio", "manifest.json");
const DEFAULT_MONTHLY_CAP = 900000;
let googleApiKeyOverride = "";
const AUDIO_PROFILES = {
  "english-balanced-v1": {
    englishVolumeGainDb: 3,
    englishWordSpeakingRate: 0.98,
    englishExampleSpeakingRate: 0.88
  },
  "english-balanced-v2": {
    englishVolumeGainDb: 5,
    englishWordSpeakingRate: 0.98,
    englishExampleSpeakingRate: 0.88
  }
};

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

function monthBucket(date = new Date()) {
  return date.toISOString().slice(0, 7);
}

function cleanText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
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
  return letters.length ? letters.join(". ") + "." : cleanText(word);
}

function ssml(segment) {
  const pause = Number(segment.pauseMs || 0);
  const breakTag = pause > 0 ? `<break time="${Math.min(pause, 10000)}ms"/>` : "";
  return `<speak>${escapeSsml(segment.text)}${breakTag}</speak>`;
}

function buildSegments(lesson, includeSpelling) {
  const segments = [
    {
      lang: "th",
      text: `เริ่ม ${lesson.category} วันที่ ${lesson.day} ฟังคำถาม แล้วตอบในใจก่อนฟังเฉลย`,
      pauseMs: 500
    }
  ];

  for (const item of lesson.items) {
    if (item.mode === "review") {
      segments.push({ lang: "th", text: `คำว่า ${item.meaning} ภาษาอังกฤษคืออะไร`, pauseMs: 3000 });
      segments.push({ lang: "en", text: item.word, pauseMs: 140 });
      segments.push({ lang: "th", text: item.meaning, pauseMs: 500 });
      continue;
    }

    segments.push({ lang: "th", text: "คำว่า", pauseMs: 50 });
    segments.push({ lang: "en", text: item.word, pauseMs: 50 });
    segments.push({ lang: "th", text: "แปลว่าอะไร", pauseMs: 3000 });
    segments.push({ lang: "en", text: item.word, pauseMs: 120 });
    if (includeSpelling) {
      segments.push({ lang: "en", text: spellForSpeech(item.word), pauseMs: 120 });
    }
    segments.push({ lang: "en", text: item.word, pauseMs: 140 });
    segments.push({ lang: "th", text: item.meaning, pauseMs: 220 });
    segments.push({ lang: "en", text: item.example, pauseMs: 150 });
    segments.push({ lang: "th", text: item.exampleTh, pauseMs: 500 });
  }

  segments.push({
    lang: "th",
    text: "จบบทนี้แล้ว ถ้ายังนึกไม่ทัน ให้ฟังซ้ำอีกรอบ",
    pauseMs: 0
  });
  return segments.map(segment => ({ ...segment, text: cleanText(segment.text) })).filter(segment => segment.text);
}

function applyAudioProfile(segments, audioProfile) {
  const profile = AUDIO_PROFILES[audioProfile];
  if (!profile) return segments;
  return segments.map(segment => {
    if (segment.lang !== "en") return segment;
    return {
      ...segment,
      speakingRate: segment.role === "example" ? profile.englishExampleSpeakingRate : profile.englishWordSpeakingRate,
      volumeGainDb: profile.englishVolumeGainDb
    };
  });
}

function buildItemSegments(item, includeSpelling, audioProfile = "") {
  const segments = [];
  if (item.mode === "review") {
    segments.push({ lang: "th", text: `คำว่า ${item.meaning} ภาษาอังกฤษคืออะไร`, pauseMs: 3000 });
    segments.push({ lang: "en", text: item.word, pauseMs: 140 });
    segments.push({ lang: "th", text: item.meaning, pauseMs: 500 });
  } else {
    segments.push({ lang: "th", text: "คำว่า", pauseMs: 50 });
    segments.push({ lang: "en", text: item.word, pauseMs: 50 });
    segments.push({ lang: "th", text: "แปลว่าอะไร", pauseMs: 3000 });
    segments.push({ lang: "en", text: item.word, pauseMs: 120 });
    if (includeSpelling) {
      segments.push({ lang: "en", text: spellForSpeech(item.word), pauseMs: 120 });
    }
    segments.push({ lang: "en", text: item.word, pauseMs: 140 });
    segments.push({ lang: "th", text: item.meaning, pauseMs: 220 });
    segments.push({ lang: "en", text: item.example, pauseMs: 150, role: "example" });
    segments.push({ lang: "th", text: item.exampleTh, pauseMs: 500 });
  }
  const cleaned = segments.map(segment => ({ ...segment, text: cleanText(segment.text) })).filter(segment => segment.text);
  return applyAudioProfile(cleaned, audioProfile);
}

function estimateChars(segments) {
  return segments.reduce((sum, segment) => sum + ssml(segment).length, 0);
}

function providerName(provider) {
  if (provider === "google") return "google-cloud-tts";
  if (provider === "amazon") return "amazon-polly";
  return provider;
}

function voiceConfig(provider, lang) {
  if (provider === "google") {
    if (lang === "en") {
      return {
        languageCode: "en-US",
        name: process.env.GOOGLE_TTS_EN_VOICE || "en-US-Chirp3-HD-Puck",
        speakingRate: Number(process.env.GOOGLE_TTS_EN_RATE || "0.98"),
        pitch: Number(process.env.GOOGLE_TTS_EN_PITCH || "0")
      };
    }
    return {
      languageCode: "th-TH",
      name: process.env.GOOGLE_TTS_TH_VOICE || "th-TH-Chirp3-HD-Puck",
      speakingRate: Number(process.env.GOOGLE_TTS_TH_RATE || "1.08"),
      pitch: Number(process.env.GOOGLE_TTS_TH_PITCH || "0")
    };
  }

  if (lang === "en") {
    return {
      languageCode: "en-US",
      voiceId: process.env.AWS_POLLY_EN_VOICE || "Joanna",
      engine: process.env.AWS_POLLY_EN_ENGINE || "neural"
    };
  }
  return {
    languageCode: "th-TH",
    voiceId: process.env.AWS_POLLY_TH_VOICE || "Niwat",
    engine: process.env.AWS_POLLY_TH_ENGINE || "neural"
  };
}

async function synthesizeGoogle(segment, outputPath) {
  const apiKey = googleApiKeyOverride || process.env.GOOGLE_TTS_API_KEY || process.env.GOOGLE_CLOUD_TTS_API_KEY;
  if (!apiKey) {
    throw new Error("Missing Google TTS API key. Set an environment variable or use --api-key-file.");
  }

  const voice = voiceConfig("google", segment.lang);
  const audioConfig = {
    audioEncoding: "MP3",
    speakingRate: Number(segment.speakingRate || voice.speakingRate)
  };
  if (Number.isFinite(Number(segment.volumeGainDb))) {
    audioConfig.volumeGainDb = Number(segment.volumeGainDb);
  }
  if (!voice.name.includes("-Chirp3-HD-")) {
    audioConfig.pitch = voice.pitch;
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

function hmac(key, value, encoding) {
  return crypto.createHmac("sha256", key).update(value, "utf8").digest(encoding);
}

function sha256(value, encoding = "hex") {
  return crypto.createHash("sha256").update(value, "utf8").digest(encoding);
}

function amzDateParts(date = new Date()) {
  const iso = date.toISOString().replace(/[:-]|\.\d{3}/g, "");
  return {
    amzDate: iso,
    dateStamp: iso.slice(0, 8)
  };
}

function signPollyRequest({ region, body, accessKeyId, secretAccessKey, sessionToken }) {
  const service = "polly";
  const host = `polly.${region}.amazonaws.com`;
  const endpoint = `https://${host}/v1/speech`;
  const { amzDate, dateStamp } = amzDateParts();
  const payloadHash = sha256(body);
  const headers = {
    "content-type": "application/json",
    host,
    "x-amz-content-sha256": payloadHash,
    "x-amz-date": amzDate
  };
  if (sessionToken) headers["x-amz-security-token"] = sessionToken;

  const signedHeaders = Object.keys(headers).sort().join(";");
  const canonicalHeaders = Object.keys(headers)
    .sort()
    .map(key => `${key}:${headers[key]}\n`)
    .join("");
  const canonicalRequest = [
    "POST",
    "/v1/speech",
    "",
    canonicalHeaders,
    signedHeaders,
    payloadHash
  ].join("\n");
  const credentialScope = `${dateStamp}/${region}/${service}/aws4_request`;
  const stringToSign = [
    "AWS4-HMAC-SHA256",
    amzDate,
    credentialScope,
    sha256(canonicalRequest)
  ].join("\n");
  const kDate = hmac(`AWS4${secretAccessKey}`, dateStamp);
  const kRegion = hmac(kDate, region);
  const kService = hmac(kRegion, service);
  const kSigning = hmac(kService, "aws4_request");
  const signature = hmac(kSigning, stringToSign, "hex");
  headers.authorization =
    `AWS4-HMAC-SHA256 Credential=${accessKeyId}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}`;
  return { endpoint, headers };
}

async function synthesizeAmazon(segment, outputPath) {
  const accessKeyId = process.env.AWS_ACCESS_KEY_ID;
  const secretAccessKey = process.env.AWS_SECRET_ACCESS_KEY;
  const sessionToken = process.env.AWS_SESSION_TOKEN;
  const region = process.env.AWS_REGION || process.env.AWS_DEFAULT_REGION || "us-east-1";
  if (!accessKeyId || !secretAccessKey) {
    throw new Error("Missing AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY");
  }

  const voice = voiceConfig("amazon", segment.lang);
  const body = JSON.stringify({
    Engine: voice.engine,
    LanguageCode: voice.languageCode,
    OutputFormat: "mp3",
    Text: ssml(segment),
    TextType: "ssml",
    VoiceId: voice.voiceId
  });
  const { endpoint, headers } = signPollyRequest({
    region,
    body,
    accessKeyId,
    secretAccessKey,
    sessionToken
  });

  const res = await fetch(endpoint, {
    method: "POST",
    headers,
    body
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Amazon Polly failed (${res.status}): ${detail.slice(0, 400)}`);
  }

  await writeFile(outputPath, Buffer.from(await res.arrayBuffer()));
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

function loadManifest(filePath, cap, bucket) {
  const manifest = readJson(filePath, null) || {};
  manifest.version = 2;
  manifest.generatedBy = "cloud-tts-batch";
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

function lessonOutputPath(lesson, includeSpelling) {
  const rel = lesson.audioFile || `audio/lessons/${lesson.categorySlug}/day-${String(lesson.day).padStart(3, "0")}.mp3`;
  const mp3Rel = rel.replace(/\\/g, "/").replace(/\.wav$/i, ".mp3");
  const variantRel = includeSpelling ? mp3Rel : mp3Rel.replace(/\.mp3$/i, "-no-spelling.mp3");
  return {
    rel: variantRel,
    abs: path.join(APP_ROOT, variantRel)
  };
}

function safeFileStem(value) {
  return cleanText(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "word";
}

function itemOutputPath(lesson, item, index, includeSpelling) {
  if (lesson.audioProfile) {
    const profile = safeFileStem(lesson.audioProfile);
    if (item.mode === "review") {
      const fileName = `${safeFileStem(item.word)}.mp3`;
      const rel = `audio/words/${lesson.categorySlug}/profiles/${profile}/review/${fileName}`;
      return { rel, abs: path.join(APP_ROOT, rel) };
    }
    const day = `day-${String(lesson.day).padStart(3, "0")}`;
    const fileName = `${String(index + 1).padStart(3, "0")}-${safeFileStem(item.word)}${includeSpelling ? "" : "-no-spelling"}.mp3`;
    const rel = `audio/words/${lesson.categorySlug}/profiles/${profile}/${day}/${fileName}`;
    return { rel, abs: path.join(APP_ROOT, rel) };
  }
  if (item.mode === "review") {
    const fileName = `${safeFileStem(item.word)}.mp3`;
    const rel = `audio/words/${lesson.categorySlug}/review/${fileName}`;
    return { rel, abs: path.join(APP_ROOT, rel) };
  }
  const day = `day-${String(lesson.day).padStart(3, "0")}`;
  const fileName = `${String(index + 1).padStart(3, "0")}-${safeFileStem(item.word)}${includeSpelling ? "" : "-no-spelling"}.mp3`;
  const rel = `audio/words/${lesson.categorySlug}/${day}/${fileName}`;
  return { rel, abs: path.join(APP_ROOT, rel) };
}

async function synthesizeSegmentsToFile({ segments, outputPath, provider, ffmpegPath, tempDir }) {
  rmSync(tempDir, { recursive: true, force: true });
  mkdirSync(tempDir, { recursive: true });
  const parts = [];
  const synthesize = provider === "amazon" ? synthesizeAmazon : synthesizeGoogle;
  try {
    for (let index = 0; index < segments.length; index += 1) {
      const segment = segments[index];
      const partPath = path.join(tempDir, `${String(index + 1).padStart(3, "0")}-${segment.lang}.mp3`);
      await synthesize(segment, partPath);
      parts.push(partPath);
    }
    await concatMp3(parts, outputPath, ffmpegPath);
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

async function generateSplitLesson({ lesson, provider, dryRun, manifest, cap, bucket, ffmpegPath, force, includeSpelling }) {
  const variantName = includeSpelling ? "withSpelling" : "withoutSpelling";
  const prepared = lesson.items.map((item, index) => {
    const segments = buildItemSegments(item, includeSpelling, lesson.audioProfile);
    const output = itemOutputPath(lesson, item, index, includeSpelling);
    const needsGeneration = !existsSync(output.abs) || (force && item.mode !== "review");
    return {
      item,
      index,
      segments,
      estimatedChars: needsGeneration ? estimateChars(segments) : 0,
      output,
      needsGeneration
    };
  });
  const estimatedChars = prepared.reduce((sum, row) => sum + row.estimatedChars, 0);
  const currentUsed = usedCharsForMonth(manifest, bucket);
  if (currentUsed + estimatedChars > cap) {
    throw new Error(`Quota guard stopped split generation: ${currentUsed + estimatedChars}/${cap}`);
  }

  console.log(`${dryRun ? "DRY" : "SPLIT"} ${lesson.id} ${variantName}: ${estimatedChars} chars, ${prepared.length} files`);
  if (dryRun) return;

  const existingEntry = manifest.lessons[lesson.id] || {};
  const existingItems = Array.isArray(existingEntry.items) ? existingEntry.items : [];
  const generatedAt = new Date().toISOString();
  const nextItems = [];

  for (const row of prepared) {
    const previous = existingItems.find(entry => entry.word === row.item.word) || {};
    if (row.needsGeneration) {
      process.stdout.write(`  ${row.index + 1}/${prepared.length} ${row.item.word} -> ${row.output.rel}\n`);
      await synthesizeSegmentsToFile({
        segments: row.segments,
        outputPath: row.output.abs,
        provider,
        ffmpegPath,
        tempDir: path.join(APP_ROOT, "audio", ".tts-parts", lesson.id, variantName, String(row.index + 1))
      });
    }
    nextItems.push({
      ...previous,
      word: row.item.word,
      order: row.index,
      mode: row.item.mode,
      [includeSpelling ? "fileWithSpelling" : "fileWithoutSpelling"]: row.output.rel
    });
  }

  const splitEntry = {
    ...existingEntry,
    category: lesson.category,
    categorySlug: lesson.categorySlug,
    day: lesson.day,
    audioProfile: lesson.audioProfile || existingEntry.audioProfile || "",
    provider: providerName(provider),
    playbackMode: "item-sequence",
    recallPauseMs: 3000,
    itemCount: lesson.items.length,
    monthBucket: bucket,
    voice: {
      en: voiceConfig(provider, "en"),
      th: voiceConfig(provider, "th")
    },
    profileSettings: AUDIO_PROFILES[lesson.audioProfile] || existingEntry.profileSettings,
    variants: {
      ...(existingEntry.variants || {}),
      [variantName]: {
        type: "item-sequence",
        estimatedChars,
        fileCount: prepared.filter(row => row.needsGeneration).length
      }
    },
    items: nextItems,
    status: "generated",
    generatedAt
  };
  delete splitEntry.file;
  delete splitEntry.fileWithSpelling;
  delete splitEntry.fileWithoutSpelling;
  delete splitEntry.includesSpelling;
  delete splitEntry.estimatedChars;
  manifest.lessons[lesson.id] = splitEntry;
  manifest.usage.push({
    lessonId: lesson.id,
    variant: variantName,
    playbackMode: "item-sequence",
    provider: providerName(provider),
    monthBucket: bucket,
    usedChars: estimatedChars,
    generatedAt
  });
  console.log(`DONE split ${lesson.id} ${variantName}`);
}

async function generateLesson({ lesson, provider, dryRun, manifest, cap, bucket, ffmpegPath, force, includeSpelling }) {
  const segments = buildSegments(lesson, includeSpelling);
  const estimatedChars = estimateChars(segments);
  const currentUsed = usedCharsForMonth(manifest, bucket);
  const { rel, abs } = lessonOutputPath(lesson, includeSpelling);
  const existingEntry = manifest.lessons[lesson.id] || {};
  const baseEntry = {
    ...existingEntry,
    category: lesson.category,
    categorySlug: lesson.categorySlug,
    day: lesson.day,
    file: existingEntry.file || (includeSpelling ? rel : undefined),
    fileWithSpelling: includeSpelling ? rel : existingEntry.fileWithSpelling,
    fileWithoutSpelling: includeSpelling ? existingEntry.fileWithoutSpelling : rel,
    provider: providerName(provider),
    playbackMode: "full-lesson",
    recallPauseMs: 3000,
    variants: {
      ...(existingEntry.variants || {}),
      [includeSpelling ? "withSpelling" : "withoutSpelling"]: {
        file: rel,
        estimatedChars
      }
    },
    itemCount: lesson.items.length,
    monthBucket: bucket,
    voice: {
      en: voiceConfig(provider, "en"),
      th: voiceConfig(provider, "th")
    }
  };

  if (currentUsed + estimatedChars > cap) {
    manifest.lessons[lesson.id] = {
      ...baseEntry,
      status: "skipped_quota",
      skippedAt: new Date().toISOString()
    };
    console.log(`SKIP quota ${lesson.id}: ${currentUsed + estimatedChars}/${cap}`);
    return;
  }

  if (existsSync(abs) && !force) {
    manifest.lessons[lesson.id] = {
      ...baseEntry,
      status: "generated",
      generatedAt: manifest.lessons[lesson.id]?.generatedAt || new Date().toISOString()
    };
    console.log(`SKIP existing ${rel}`);
    return;
  }

  if (dryRun) {
    console.log(`DRY ${lesson.id}: ${estimatedChars} chars -> ${rel}`);
    return;
  }

  const tempDir = path.join(APP_ROOT, "audio", ".tts-parts", lesson.id);
  rmSync(tempDir, { recursive: true, force: true });
  mkdirSync(tempDir, { recursive: true });

  const parts = [];
  const synthesize = provider === "amazon" ? synthesizeAmazon : synthesizeGoogle;
  try {
    for (let index = 0; index < segments.length; index += 1) {
      const segment = segments[index];
      const partPath = path.join(tempDir, `${String(index + 1).padStart(3, "0")}-${segment.lang}.mp3`);
      process.stdout.write(`  ${index + 1}/${segments.length} ${segment.lang} ${segment.text.slice(0, 48)}\n`);
      await synthesize(segment, partPath);
      parts.push(partPath);
    }
    await concatMp3(parts, abs, ffmpegPath);
    const generatedAt = new Date().toISOString();
    manifest.lessons[lesson.id] = {
      ...baseEntry,
      status: "generated",
      generatedAt
    };
    manifest.usage.push({
      lessonId: lesson.id,
      provider: providerName(provider),
      monthBucket: bucket,
      usedChars: estimatedChars,
      generatedAt
    });
    console.log(`DONE ${rel}`);
  } catch (error) {
    manifest.lessons[lesson.id] = {
      ...baseEntry,
      status: "failed",
      failedAt: new Date().toISOString(),
      error: error.message
    };
    throw error;
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const provider = String(args.provider || process.env.TTS_PROVIDER || "google").toLowerCase();
  if (!["google", "amazon"].includes(provider)) {
    throw new Error("--provider must be google or amazon");
  }

  const cap = Number(args["month-cap"] || process.env.MONTHLY_TTS_CHAR_CAP || DEFAULT_MONTHLY_CAP);
  const bucket = String(args.month || process.env.TTS_MONTH_BUCKET || monthBucket());
  const jobsPath = path.resolve(args.jobs || DEFAULT_JOB);
  const manifestPath = path.resolve(args.manifest || DEFAULT_MANIFEST);
  const apiKeyFile = args["api-key-file"] ? path.resolve(args["api-key-file"]) : "";
  const dryRun = Boolean(args["dry-run"]);
  const force = Boolean(args.force);
  const includeSpelling = String(args.spelling || "on").toLowerCase() !== "off";
  const splitItems = Boolean(args["split-items"]);
  const onlyCategory = args["only-category"] || "";
  const onlyDay = Number(args["only-day"] || 0);
  const limit = Number(args.limit || 0);
  const ffmpegPath = findFfmpeg(args.ffmpeg);

  if (provider === "google" && apiKeyFile) {
    googleApiKeyOverride = (await readFile(apiKeyFile, "utf8")).trim();
  }

  const jobs = JSON.parse(await readFile(jobsPath, "utf8"));
  let lessons = Array.isArray(jobs.lessons) ? jobs.lessons : [jobs];
  if (onlyCategory) lessons = lessons.filter(lesson => lesson.categorySlug === onlyCategory || lesson.category === onlyCategory);
  if (onlyDay) lessons = lessons.filter(lesson => Number(lesson.day) === onlyDay);
  if (limit) lessons = lessons.slice(0, limit);
  if (!lessons.length) throw new Error("No lessons matched the filters");

  const manifest = loadManifest(manifestPath, cap, bucket);
  await mkdir(path.dirname(manifestPath), { recursive: true });

  console.log(`Provider: ${providerName(provider)}`);
  console.log(`Month cap: ${usedCharsForMonth(manifest, bucket)}/${cap} chars in ${bucket}`);
  console.log(`ffmpeg: ${ffmpegPath || "not found; binary concat fallback"}`);

  for (const lesson of lessons) {
    if (splitItems) {
      await generateSplitLesson({ lesson, provider, dryRun, manifest, cap, bucket, ffmpegPath, force, includeSpelling });
    } else {
      await generateLesson({ lesson, provider, dryRun, manifest, cap, bucket, ffmpegPath, force, includeSpelling });
    }
    if (!dryRun) writeJson(manifestPath, manifest);
  }

  if (dryRun) {
    console.log("Dry run complete. Manifest was not changed.");
  } else {
    writeJson(manifestPath, manifest);
    console.log(`Wrote ${path.relative(APP_ROOT, manifestPath)}`);
  }
}

main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
