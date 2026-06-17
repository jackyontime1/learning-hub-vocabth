import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const readerRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const workspaceRoot = path.resolve(readerRoot, "..");
const podcastRoot = path.join(workspaceRoot, "deploy-rollback-original");
const audioPublicPrefix = "podcast/";

const appPath = path.join(podcastRoot, "app.js");
const appCode = fs.readFileSync(appPath, "utf8");
const dataStart = appCode.indexOf("const thaiPack = {");
const dataEnd = appCode.indexOf("const state = {", dataStart);
if (dataStart < 0 || dataEnd < 0) {
  throw new Error("Could not locate podcast data block in app.js");
}

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(`${appCode.slice(dataStart, dataEnd)}
globalThis.out = { thaiPack, categoryOrder, customPack, customCategoryMap, extraCustomPack };
`, sandbox);

const { thaiPack, categoryOrder, customPack, customCategoryMap, extraCustomPack } = sandbox.out;
const oxfordWords = fs.readFileSync(path.join(podcastRoot, "oxford3000.txt"), "utf8")
  .split(/\r?\n/)
  .map(cleanWord)
  .filter(Boolean);
const oxfordMetadata = readJson(path.join(podcastRoot, "oxford-metadata.json"), { entries: {} });
const oxfordTranslations = readJson(path.join(podcastRoot, "oxford-translations.json"), { entries: {} });
const audioManifest = readJson(path.join(podcastRoot, "audio", "manifest.json"), { lessons: {} });

function readJson(file, fallback) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return fallback;
  }
}

function cleanWord(raw = "") {
  return String(raw).replace(/\s+[12]$/, "").replace(/[^\w\s.'-]/g, "").trim();
}

function wordKey(category, word) {
  return `${category}::${cleanWord(word).toLowerCase()}`;
}

function audioIndex() {
  const byKey = new Map();
  Object.values(audioManifest.lessons || {}).forEach((lesson) => {
    const category = lesson.category;
    (lesson.items || []).forEach((item) => {
      const key = wordKey(category, item.word);
      const current = byKey.get(key);
      const next = {
        day: Number(lesson.day) || null,
        withSpelling: item.fileWithSpelling || "",
        withoutSpelling: item.fileWithoutSpelling || item.fileWithSpelling || "",
        provider: lesson.provider || "",
      };
      if (!current || item.mode === "full") byKey.set(key, next);
    });
  });
  return byKey;
}

const audioByKey = audioIndex();
const cardsByKey = new Map();

function addCard(row) {
  const key = wordKey(row.category, row.word);
  if (!row.word || !row.category || cardsByKey.has(key)) return;
  const audio = audioByKey.get(key) || {};
  cardsByKey.set(key, {
    id: key,
    word: cleanWord(row.word),
    meaning: row.meaning || "ยังไม่มีคำแปลไทย",
    category: row.category,
    day: row.day || audio.day || null,
    source: row.source || "podcast",
    order: Number.isFinite(row.order) ? row.order : null,
    frequencyRank: Number.isFinite(row.frequencyRank) ? row.frequencyRank : null,
    example: row.example || "",
    exampleTh: row.exampleTh || "",
    hasCuratedExample: Boolean(row.example && row.exampleTh),
    audioWithSpelling: audio.withSpelling ? `${audioPublicPrefix}${audio.withSpelling}` : "",
    audioWithoutSpelling: audio.withoutSpelling ? `${audioPublicPrefix}${audio.withoutSpelling}` : "",
    audioProvider: audio.provider || "",
  });
}

Object.entries(customPack || {}).forEach(([packKey, rows]) => {
  const category = customCategoryMap[packKey];
  [...rows, ...((extraCustomPack || {})[packKey] || [])].forEach((row, index) => {
    addCard({
      word: row[0],
      meaning: row[1],
      example: row[2],
      exampleTh: row[3],
      category,
      order: index,
      source: "podcast-custom",
    });
  });
});

const seenOxford = new Set();
oxfordWords.forEach((word, index) => {
  const lower = word.toLowerCase();
  if (seenOxford.has(lower)) return;
  seenOxford.add(lower);
  const meta = oxfordMetadata.entries?.[lower] || {};
  const translation = oxfordTranslations.entries?.[lower] || {};
  const packed = thaiPack[lower];
  const category = meta.category || packed?.[4] || "Starter Everyday";
  addCard({
    word,
    meaning: translation.meaning || packed?.[1] || "ยังไม่มีคำแปลไทย",
    example: packed?.[2] || "",
    exampleTh: translation.exampleTh || packed?.[3] || "",
    category,
    order: index,
    frequencyRank: meta.categoryRank || index + 1,
    source: "podcast-oxford",
  });
});

const cards = [...cardsByKey.values()].sort((a, b) => {
  const categoryDiff = categoryOrder.indexOf(a.category) - categoryOrder.indexOf(b.category);
  if (categoryDiff) return categoryDiff;
  return (a.frequencyRank ?? a.order ?? 0) - (b.frequencyRank ?? b.order ?? 0);
});

const categories = categoryOrder
  .map((name) => ({ name, count: cards.filter((card) => card.category === name).length }))
  .filter((row) => row.count > 0);

const payload = {
  version: 1,
  generatedAt: new Date().toISOString(),
  source: "deploy-rollback-original podcast data",
  categories,
  cards,
};

const outputs = [
  path.join(readerRoot, "static", "data", "podcast-flashcards.json"),
  path.join(readerRoot, "site", "data", "podcast-flashcards.json"),
];

for (const output of outputs) {
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}

console.log(JSON.stringify({
  cards: cards.length,
  categories: categories.length,
  outputs,
}, null, 2));
