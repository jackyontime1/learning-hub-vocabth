#!/usr/bin/env node
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const APP_ROOT = path.resolve(SCRIPT_DIR, "..");
const APP_JS = path.join(APP_ROOT, "app.js");
const OUTPUT = path.join(APP_ROOT, "audio", "jobs", "job-interview-qanda-days-002-008.json");
const BATCH_SIZE = 10;
const REVIEW_CAP = 50;
const DAY_AUDIO_PROFILES = {
  2: "english-balanced-v2"
};

function extractArray(source, declaration, property) {
  const declarationStart = source.indexOf(declaration);
  if (declarationStart < 0) throw new Error(`Missing declaration: ${declaration}`);

  const propertyStart = source.indexOf(`${property}:`, declarationStart);
  if (propertyStart < 0) throw new Error(`Missing property: ${property}`);

  const arrayStart = source.indexOf("[", propertyStart);
  let depth = 0;
  let inString = false;
  let escaped = false;

  for (let index = arrayStart; index < source.length; index += 1) {
    const char = source[index];
    if (inString) {
      if (escaped) escaped = false;
      else if (char === "\\") escaped = true;
      else if (char === "\"") inString = false;
      continue;
    }

    if (char === "\"") {
      inString = true;
      continue;
    }
    if (char === "[") depth += 1;
    if (char === "]") {
      depth -= 1;
      if (depth === 0) return JSON.parse(source.slice(arrayStart, index + 1));
    }
  }

  throw new Error(`Unclosed array: ${declaration}.${property}`);
}

function toItem(row, mode) {
  const [word, meaning, example, exampleTh] = row;
  return { word, meaning, example, exampleTh, mode };
}

function buildLesson(words, day) {
  const todayStart = (day - 1) * BATCH_SIZE;
  const todayEnd = Math.min(todayStart + BATCH_SIZE, words.length);
  const today = words.slice(todayStart, todayEnd).map(row => toItem(row, "full"));
  const reviewLimit = Math.max(0, REVIEW_CAP - today.length);
  const reviewStart = Math.max(0, todayStart - reviewLimit);
  const previous = words.slice(reviewStart, todayStart).map(row => toItem(row, "review"));

  return {
    id: `job-interview-qanda__day-${String(day).padStart(3, "0")}`,
    category: "Job Interview Q&A",
    categorySlug: "job-interview-qanda",
    day,
    ...(DAY_AUDIO_PROFILES[day] ? { audioProfile: DAY_AUDIO_PROFILES[day] } : {}),
    batchSize: BATCH_SIZE,
    items: [...previous, ...today]
  };
}

const source = await readFile(APP_JS, "utf8");
const primary = extractArray(source, "const customPack =", "interview");
const extra = extractArray(source, "const extraCustomPack =", "interview");
const words = [...primary, ...extra];

if (words.length < 71) {
  throw new Error(`Expected at least 71 interview entries, found ${words.length}`);
}

const finalDay = Math.ceil(words.length / BATCH_SIZE);
const lessons = Array.from({ length: finalDay - 1 }, (_, index) => buildLesson(words, index + 2));
await writeFile(OUTPUT, `${JSON.stringify({
  version: 1,
  app: "VocabTH / Oxford Audio Vocabulary",
  scope: "job-interview-days-2-8",
  lessons
}, null, 2)}\n`, "utf8");

for (const lesson of lessons) {
  const review = lesson.items.filter(item => item.mode === "review").length;
  const full = lesson.items.filter(item => item.mode === "full").length;
  console.log(`Day ${lesson.day}: ${lesson.items.length} items (${review} review, ${full} full)`);
}
console.log(`Wrote ${path.relative(APP_ROOT, OUTPUT)}`);
