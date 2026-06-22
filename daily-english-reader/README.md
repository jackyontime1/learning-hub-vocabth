# Daily English Reader

A static, free-only English news reader for Thai learners. The daily build creates ten stories: two each for A1, A2, B1, B2, and C1. It never calls a paid fallback or enables automatic billing.

## Free provider chain

- General news: Currents, then Guardian Open Platform.
- Science and technology: NASA, then arXiv.
- Weather and environment: US National Weather Service.
- World events and earthquakes: USGS.
- Images: source media, Openverse, Wikimedia Commons, optional free Unsplash, optional local Stable Diffusion, then a unique local SVG fallback.
- Translation: full-article Thai translation from the local `facebook/nllb-200-distilled-600M` model. Production fails safely instead of publishing a placeholder when translation is unavailable.
- Speech: browser/iPhone Web Speech is used first for smoother playback; generated audio is optional fallback only.
- Level adaptation: summa/TextRank and deterministic heuristics. Ollama is optional and local.

The updater fetches providers in batches and selects content locally. Provider usage, errors, cooldowns, and soft limits are stored in `data/quota/YYYY-MM-DD.json`.

## Output

```text
site/
  index.html
  daily.html
  vocabulary.html
  flashcards.html
  saved.html
  podcast/index.html
  podcast/audio/manifest.json
  podcast/audio/words/...
  _headers
  content-index.json
  data/podcast-flashcards.json
  provider-status.json
  news/YYYY-MM-DD/article-slug/
    index.html
    article.json
    a2.mp3
```

The browser stores saved stories, saved words, flashcard progress, font size, and audio speed in versioned localStorage keys.

## Install

Python 3.11 is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install transformers sentencepiece
```

Install `ffmpeg` and either an English system voice or `espeak-ng`. Set `READING_TRANSLATION_PROVIDER=nllb` to use the local English-to-Thai model. The model downloads to the Hugging Face cache on first use.

Copy `.env.example` to `.env`. Add only the free API keys you have. Missing providers are skipped.

For unique images generated on your own computer, start Stable Diffusion WebUI with
its API enabled (`--api`) and set `LOCAL_IMAGE_API_URL`, commonly
`http://127.0.0.1:7860`. The generated image is cached by article ID, so rebuilding
the same story does not spend GPU time again. Leave the setting empty on machines
without a local image generator; the free image-source chain remains active.

```powershell
python update_site.py
python -m http.server 8092 --directory site
```

Open `http://127.0.0.1:8092/`.

## Offline demo

The demo uses six fixtures, local images, local translation fixtures, and skips real audio generation:

```powershell
$env:FREE_ONLY="1"
$env:DEMO_MODE="1"
$env:SKIP_AUDIO="1"
python update_site.py
```

## Safety and failure behavior

- `FREE_ONLY=0` is rejected.
- HTTP 401/403 disables that provider until its key is fixed.
- HTTP 429 pauses the provider until the next UTC quota window.
- Timeouts and server errors use bounded retries, then switch provider.
- Text, image, and translation results are cached.
- A new edition is built in `.site-staging`.
- If the build does not contain exactly two stories per level or required files are missing, `site/` is left unchanged.

## Pages

- Home: two stories per level, a latest-seven-days date selector, category filters, and level filters. A1/C1 are displayed as unavailable until those generators are added.
- Daily Reading: all stories from the latest seven days.
- Vocabulary: saved words with search, pronunciation, and remove controls.
- Podcast: the MP3 vocabulary podcast app mounted inside the same Learning Hub at `podcast/index.html`.
- Flashcards: Anki-style podcast vocabulary review from the generated podcast flashcard deck.
- Saved News: saved story cards with remove controls.
- Article: every English word is clickable, full Thai translation, saved-word review, font controls, and MP3 speed at 0.75x, 1x, or 1.25x.

## Learning Hub build

Build the combined static site before Cloudflare Pages preview or deploy:

```powershell
node scripts\build-learning-hub.mjs
```

This command refreshes the Podcast flashcard deck, mounts the Podcast app under `site/podcast/`, copies the current MP3 manifest/audio paths, and writes Cloudflare Pages headers to `site/_headers`.

Generated Learning Hub pages add `?v=20260617-learning-hub` to local CSS/JS assets so phones do not keep using stale cached files from the previous site shape.

The Cloudflare Pages output directory is `site`. For an R2-backed production setup, keep public audio paths compatible with `/podcast/audio/words/...` and configure R2 CORS for `GET`, `HEAD`, `OPTIONS`, and the `Range` header so iPhone playback can seek and resume reliably.

To rebuild only the static flashcard deck from the Podcast project:

```powershell
node scripts\build-podcast-flashcards.mjs
```

The generated deck is written to `static/data/podcast-flashcards.json` and `site/data/podcast-flashcards.json`.

## GitHub Actions to Cloudflare Pages

The included workflow runs at 05:00 in `America/Toronto`, runs unit tests, builds the daily reading site from free news sources, merges the Podcast/Flashcards Learning Hub, persists the rolling data cache, and deploys `site/` to Cloudflare Pages project `learning-hub-vocabth`.

Required secrets under **Settings > Secrets and variables > Actions**:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

Optional free content/image provider keys:

- `CURRENTS_API_KEY`
- `GUARDIAN_API_KEY`
- `NASA_API_KEY` (optional; `DEMO_KEY` works with a smaller NASA limit)
- `UNSPLASH_ACCESS_KEY`

The workflow keeps `FREE_ONLY=1`, `DEMO_MODE=0`, `SKIP_AUDIO=1`, and `REQUIRE_FULL_TRANSLATION=1`. It runs the NLLB English-to-Thai model locally inside GitHub Actions and caches the model, so the article body must have a real Thai translation before deployment. Reading playback uses browser/iPhone Web Speech first and keeps a tiny placeholder audio file only for static page compatibility. It does not use the OpenAI API, Podcast Google Cloud TTS key, or Podcast monthly safety cap. The selected model is licensed CC-BY-NC-4.0 and is intended here for this personal, non-commercial learning project.

If the GitHub repository root is the parent project folder, use `.github/workflows/daily-update.yml`. If the repository root is `daily-english-reader`, use `daily-english-reader/.github/workflows/daily-update.yml` and make sure the Podcast source folder is available at `../deploy-rollback-original` for the combined Learning Hub build.

## Tests

```powershell
python -m unittest discover -s tests -v
node --check static\js\app.js
```

The tests cover quota resets, auth/rate-limit handling, free-only enforcement, six-story selection, word wrapping, and preservation of the existing site when staging validation fails.

## Licensing note

This configuration assumes personal, non-commercial use. Review every provider license before adding advertising, subscriptions, or business use. The site links back to every source and identifies government reports and research summaries.
