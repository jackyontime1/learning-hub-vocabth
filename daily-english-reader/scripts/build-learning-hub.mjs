import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const readerRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const workspaceRoot = path.resolve(readerRoot, "..");
const podcastRoot = path.join(workspaceRoot, "deploy-rollback-original");
const siteRoot = path.join(readerRoot, "site");
const podcastSiteRoot = path.join(siteRoot, "podcast");
const assetVersion = "20260617-learning-hub";

function copyFile(source, target) {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.copyFileSync(source, target);
}

function copyDir(source, target) {
  fs.rmSync(target, { recursive: true, force: true });
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.cpSync(source, target, { recursive: true });
}

function buildReaderNav(basePrefix = "../", active = "podcast") {
  const nav = [
    ["index", "index.html", "fa-solid fa-house", "Home"],
    ["daily", "daily.html", "fa-regular fa-calendar", "Daily Reading"],
    ["vocabulary", "vocabulary.html", "fa-solid fa-cube", "Vocabulary"],
    ["podcast", "podcast/index.html", "fa-solid fa-microphone-lines", "Podcast"],
    ["flashcards", "flashcards.html", "fa-regular fa-clone", "Flashcards"],
    ["saved", "saved.html", "fa-regular fa-bookmark", "Saved"],
  ];
  return `<header class="site-header">
      <a class="brand" href="${basePrefix}index.html">
        <span class="brand-mark"><i class="fa-solid fa-book-open"></i></span>
        <span><strong>Read English Daily</strong><small>Learning Hub</small></span>
      </a>
      <nav class="main-nav" aria-label="Main navigation">
        ${nav.map(([key, href, icon, label]) => {
          const resolved = key === "podcast" ? `${basePrefix}${href}` : `${basePrefix}${href}`;
          const classes = [active === key ? "active" : "", key === "podcast" ? "podcast-nav" : ""].filter(Boolean).join(" ");
          return `<a class="${classes}" href="${resolved}"><i class="${icon}"></i><span>${label}</span></a>`;
        }).join("\n        ")}
      </nav>
      <span class="profile-button" aria-hidden="true"><i class="fa-solid fa-user"></i></span>
    </header>`;
}

function buildPodcastPage() {
  fs.rmSync(podcastSiteRoot, { recursive: true, force: true });
  fs.mkdirSync(podcastSiteRoot, { recursive: true });
  for (const name of ["app.js", "styles.css", "oxford3000.txt", "oxford-metadata.json", "oxford-translations.json"]) {
    copyFile(path.join(podcastRoot, name), path.join(podcastSiteRoot, name));
  }
  copyFile(path.join(podcastRoot, "audio", "manifest.json"), path.join(podcastSiteRoot, "audio", "manifest.json"));
  copyDir(path.join(podcastRoot, "audio", "words"), path.join(podcastSiteRoot, "audio", "words"));

  let html = fs.readFileSync(path.join(podcastRoot, "index.html"), "utf8");
  html = html.replace("<title>Oxford Audio Vocabulary</title>", "<title>Podcast Vocabulary | Read English Daily</title>");
  html = html.replace('<link rel="stylesheet" href="./styles.css" />', `<link rel="stylesheet" href="../static/css/styles.css?v=${assetVersion}" />\n    <link rel="stylesheet" href="./styles.css" />`);
  html = html.replace("<body>", '<body data-page="podcast" data-base-prefix="../">');
  html = html.replace('<main class="shell">', `${buildReaderNav("../", "podcast")}\n    <main class="shell podcast-shell">`);
  fs.writeFileSync(path.join(podcastSiteRoot, "index.html"), html, "utf8");
}

function updateGeneratedNav() {
  const htmlFiles = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      if (entry.isFile() && entry.name.endsWith(".html")) htmlFiles.push(full);
    }
  };
  walk(siteRoot);
  for (const file of htmlFiles) {
    if (file.includes(`${path.sep}podcast${path.sep}`)) continue;
    const relative = path.relative(path.dirname(file), siteRoot) || ".";
    const basePrefix = relative === "." ? "" : `${relative.replaceAll(path.sep, "/")}/`;
    let html = fs.readFileSync(file, "utf8");
    html = html.replace(/<nav class="main-nav" aria-label="Main navigation">[\s\S]*?<\/nav>/, buildReaderNav(basePrefix, pageType(html)).match(/<nav[\s\S]*<\/nav>/)[0]);
    html = versionLearningHubAssets(html);
    fs.writeFileSync(file, html, "utf8");
  }
}

function versionLearningHubAssets(html) {
  return html
    .replace(/(href="[^"]*static\/css\/styles\.css)(?:\?v=[^"]*)?"/g, `$1?v=${assetVersion}"`)
    .replace(/(src="[^"]*static\/js\/app\.js)(?:\?v=[^"]*)?"/g, `$1?v=${assetVersion}"`);
}

function pageType(html) {
  const match = html.match(/<body[^>]*data-page="([^"]+)"/);
  return match?.[1] || "";
}

function writeCloudflareFiles() {
  fs.writeFileSync(path.join(siteRoot, "_headers"), `# Cloudflare Pages headers for Learning Hub
/podcast/audio/*
  Access-Control-Allow-Origin: *
  Access-Control-Allow-Methods: GET, HEAD, OPTIONS
  Access-Control-Allow-Headers: Range, Content-Type
  Accept-Ranges: bytes
  Cache-Control: public, max-age=31536000, immutable

/data/*
  Access-Control-Allow-Origin: *
  Cache-Control: public, max-age=300

/*.html
  Cache-Control: public, max-age=0, must-revalidate
`, "utf8");
}

execFileSync("node", [path.join(readerRoot, "scripts", "build-podcast-flashcards.mjs")], { stdio: "inherit" });
buildPodcastPage();
updateGeneratedNav();
writeCloudflareFiles();

console.log(JSON.stringify({
  siteRoot,
  podcastPage: path.join(podcastSiteRoot, "index.html"),
  headers: path.join(siteRoot, "_headers"),
}, null, 2));
