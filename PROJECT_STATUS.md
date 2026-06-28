# VocabTH / Podcast Voice - Project Status

Updated: June 28, 2026

## Workspace

- Working directory: `D:\podcast voice`
- Production source: `D:\podcast voice\deploy-rollback-original`
- Production URL: https://fabulous-tanuki-b7a44d.netlify.app
- Netlify site ID: `a3efdc09-9ec8-4e20-a27e-1f69f554d54b`
- Netlify CLI and direct API can access the site, but Netlify currently blocks new deploys because the account credit usage has been exceeded.
- Exact API response on June 12, 2026:
  `Account credit usage exceeded - new deploys are blocked until credits are added`
- Local Oxford translation changes are ready but not yet live.
- Prepared deploy package:
  `D:\podcast voice\outputs\vocabth-oxford-natural-thai-deploy-20260612-continue.zip`

## Current Scope

- Static audio-first vocabulary web app.
- Around 4,083 vocabulary entries.
- Oxford entries now use generated category metadata and no longer rely on the `Full Oxford Base` UI bucket.
- Job Interview Q&A contains 71 words across 8 days.
- Construction and Oxford categories still use Web Speech unless an MP3 manifest entry exists.
- Daily English Reader now has a local Flashcards page for podcast vocabulary:
  `D:\podcast voice\daily-english-reader\site\flashcards.html`
- Flashcards data is generated from Podcast categories into:
  `D:\podcast voice\daily-english-reader\site\data\podcast-flashcards.json`
- Current Flashcards payload: 4,130 cards across 11 Podcast categories.
- Flashcards progress is stored in browser localStorage key:
  `learnhub.flashcards.v1`
- Learning Hub now has a Cloudflare Pages-ready local build that combines Reading, Podcast, Vocabulary, Flashcards, and Saved under one static site:
  `D:\podcast voice\daily-english-reader\site`
- Podcast is available inside the same site at:
  `D:\podcast voice\daily-english-reader\site\podcast\index.html`
- Podcast audio paths for Flashcards now use same-site paths such as:
  `podcast/audio/words/...`
- Cloudflare Pages headers are generated at:
  `D:\podcast voice\daily-english-reader\site\_headers`
- Learning Hub CSS/JS assets are versioned with `?v=20260617-learning-hub` to avoid stale browser cache on iPhone after moving from the old Netlify Podcast URL.
- No Cloudflare deploy has been performed yet because Cloudflare Pages/R2 credentials and bucket config are not set in this workspace.
- Cloudflare Pages deploy was performed on June 17, 2026.
- Cloudflare Pages project:
  `learning-hub-vocabth`
- Cloudflare Pages production URL:
  `https://learning-hub-vocabth.pages.dev/`
- First deployment URL:
  `https://0e97e168.learning-hub-vocabth.pages.dev`
- R2 is not enabled yet on the Cloudflare account. Wrangler returned:
  `Please enable R2 through the Cloudflare Dashboard. [code: 10042]`
- Daily Reading automation has been configured for GitHub Actions -> Cloudflare Pages.
- Automation schedule:
  `05:17 America/Toronto` (avoids the top-of-hour GitHub Actions queue)
- GitHub Actions uses a timezone-aware `17 5 * * *` schedule for `America/Toronto` and also supports manual or main-branch push runs.
- Automation deploy target:
  `https://learning-hub-vocabth.pages.dev/`
- Reading automation uses browser/iPhone Web Speech (`SKIP_AUDIO=1`) and does not generate MP3 or consume the Podcast Google Cloud TTS monthly safety cap.
- Automation uses the free image chain: source media, Openverse, Wikimedia Commons, optional free Unsplash, optional local Stable Diffusion, then a unique local SVG fallback.
- GitHub repository:
  `https://github.com/jackyontime1/learning-hub-vocabth`
- GitHub Actions repository secrets are configured:
  `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`
- The workflow now runs a no-audio preflight build before the real Reading audio build and Cloudflare Pages deploy.
- First manual GitHub Actions run succeeded on June 17, 2026:
  `https://github.com/jackyontime1/learning-hub-vocabth/actions/runs/27692710821`
- The successful run generated and persisted six free Reading audio files for `2026-06-17`, then deployed the combined Learning Hub to Cloudflare Pages.
- The successful run did not use Google Cloud TTS and did not consume the Podcast monthly TTS safety cap.
- Issue found after first run: `2026-06-17` repeated the demo/fallback stories from `2026-06-14` because no free news API keys were configured and production allowed `demo_articles()` as fallback.
- Fix in progress: production Daily Reading now pulls real RSS news from free sources first, demo content is limited to `DEMO_MODE=1`, and demo-only editions are removed once a real edition is generated.
- Reading fix prepared on June 18, 2026:
  - GitHub Actions now cleans preflight no-audio output before the production build.
  - Manual/production workflow runs set `REFRESH_TODAY=1` so stale demo/silent output is replaced.
  - Production Reading validation now requires real `.mp3` files for non-demo articles.
  - Vocabulary popups now include local part-of-speech labels such as `n.`, `v.`, `adj.`, and `adv.`.
  - RSS source chain now includes CBC News, BBC News, and NPR before optional API-key providers.
  - This does not use Google Cloud TTS and does not consume the Podcast monthly TTS safety cap.
- Reading fix deployed on June 18, 2026:
  - GitHub Actions run:
    `https://github.com/jackyontime1/learning-hub-vocabth/actions/runs/27735481088`
  - Cloudflare preview deployment:
    `https://75d17c08.learning-hub-vocabth.pages.dev`
  - Production URL remains:
    `https://learning-hub-vocabth.pages.dev/`

## Reading Content Model Round 2A - June 28, 2026

- Round 2A: Reading Content Model Redesign is complete and production-verified.
- Commit:
  `d104c978b6146fcbf8fbcf3f50fd98020ee65ebf`
- Commit message:
  `Redesign Daily Reader content model`
- GitHub Actions run:
  `https://github.com/jackyontime1/learning-hub-vocabth/actions/runs/28308679408`
- Workflow result: success.
  - `should-run`: success
  - Preflight no-audio build: success
  - Build daily reader: success
  - Preview deploy and verification: success
  - Production deploy: success
  - Verify production: success
  - Rolling cache persistence: success
- Production verification passed:
  - Latest date: `2026-06-27`
  - Retained stories: 70
  - Latest-day stories: 10
  - A1/A2/B1/B2/C1: 2 each
  - Schema version: 10 for all articles
  - Complete full-body `thai_text`: passed
  - Placeholder or incomplete Thai: none
  - `useful_phrases`: 3-5 per reading; validation passed
  - Useful-phrase source matching and Thai quality: passed
  - Article template shows `แปลไทยทั้งบท`
  - Useful-phrases section is visible
- A1 and A2 are planned first-class bilingual daily-life practice content, not operational fallback:
  - `readingType`: `daily_life_practice_story`
  - `contentType`: `fictional_practice_story`
  - `isRealNews`: `false`
  - `isFallback`: `false`
- B1 remains real-news based:
  - `readingType`: `easy_news`
  - `isRealNews`: `true`
- B2 remains real-news based:
  - `readingType`: `real_news`
  - `isRealNews`: `true`
- C1 remains real-news based:
  - `readingType`: `advanced_real_news`
  - `isRealNews`: `true`
- Implementation summary:
  - A1/A2 use curated bilingual daily-life practice stories.
  - B1/B2/C1 remain real-news based by level.
  - Thai translation is stored as full-body `thai_text`, not a summary.
  - Schema 10 adds `useful_phrases` with source-matching validation.
  - The production verifier now checks schema 10 and reading classification.
  - Workflow assertions now require schema 10.
  - New content file: `daily-english-reader/content/practice-stories.json`
- Repository safety note:
  - The original source repository at `D:\podcast voice` remains contaminated and must not be used for commits until it is cleaned separately.
  - The clean repository at `D:\codex-clean-round2a-20260628` was used for the safe Round 2A commit and push.
  - Prefer drive D for future clean clones, temporary worktrees, patches, logs, outputs, and backups.
- Free-only production constraints remain:
  - `FREE_ONLY=1`
  - `DEMO_MODE=0`
  - `SKIP_AUDIO=1`
  - `REQUIRE_FULL_TRANSLATION=1`
  - No OpenAI API
  - No paid translation, image, or audio APIs
  - No paid storage risk

## Oxford Category Distribution

- Oxford source file contains 3,837 unique entries after cleanup.
- `Full Oxford Base` has been removed from the active category selector.
- Oxford entries are now distributed across 8 general categories and sorted by frequency rank within each category.
- The `translated only` filter now applies only to the 3 protected categories, so Oxford general categories show the full frequency-ranked lists on the website.
- Oxford Thai translation payload now covers all 3,837 entries in:
  `D:\podcast voice\deploy-rollback-original\oxford-translations.json`
- Translation coverage breakdown:
  - Preserved curated Thai entries from `thaiPack`: 185
  - Generated Thai meanings for missing Oxford entries: 3,652
  - Unresolved entries: 0
- For Oxford entries without curated examples, the UI now shows the word and Thai meaning only, and playback skips fake placeholder sentences so the lesson sounds less robotic.
- Current Oxford category counts:
  - `Starter Everyday`: 2,458
  - `Work & Study`: 441
  - `People & Feelings`: 235
  - `Travel & Places`: 107
  - `Home & Food`: 88
  - `Nature & Health`: 104
  - `Actions & Thinking`: 316
  - `Society & Media`: 88
- Category metadata file:
  `D:\podcast voice\deploy-rollback-original\oxford-metadata.json`
- Metadata generator:
  `D:\podcast voice\deploy-rollback-original\scripts\generate-oxford-metadata.py`
- Translation generator:
  `D:\podcast voice\deploy-rollback-original\scripts\generate-oxford-translations.py`

## Job Interview Audio

- Days 1-8 use pre-generated Google Cloud Text-to-Speech MP3 files.
- Voice: Google Chirp 3 HD Puck.
- English: `en-US-Chirp3-HD-Puck`.
- Thai: `th-TH-Chirp3-HD-Puck`.
- Audio is split into one file per queue item.
- Users can start from any word in the queue.
- Users can enable or disable spelling for current-day words.
- Playback speed control: `0.75x` to `1.25x`.
- Recall pause: 3 seconds.
- Previous-day words use short review audio.
- Current-day words use full audio with examples.
- Queue is capped at 50 words:
  - Day 2: 20
  - Day 3: 30
  - Day 4: 40
  - Days 5-8: 50

## Day 2 Audio Trial

Job Interview Day 2 currently uses profile `english-balanced-v2`:

- All English speech volume: `+5 dB`.
- English vocabulary speed: `0.98`.
- English example sentence speed: `0.88`.
- Thai speed remains `1.08`.
- Both spelling and no-spelling variants were generated.
- The new files were deployed to production on June 12, 2026.
- This profile is isolated to Day 2 and does not change Days 1 or 3-8.

The user should test Day 2 on an iPhone again before this profile is copied to other days.

## Headset Pause / Resume

- The web app now registers Media Session play, pause, stop, previous, and next handlers in `app.js`.
- This was added because the old web player only handled the on-page buttons and did not expose proper headset / lock-screen controls like YouTube or native audio apps.
- MP3 playback now uses one persistent hidden `<audio>` element instead of creating new audio objects for each play action.
- Job Interview lessons should now pause and resume from Bluetooth headset controls more consistently when using the MP3 lesson flow.
- Categories that still fall back to Web Speech may not behave as reliably as MP3-backed lessons on iPhone.

## TTS Quota

- Monthly safety cap: 900,000 characters.
- June 2026 usage recorded in manifest: 131,946 characters.
- Remaining safety allowance: 768,054 characters.
- Daily Oxford MP3 automation is active:
  - Automation ID: `oxford-mp3-daily-batch`
  - Schedule: daily at 09:00 Asia/Bangkok.
  - Maximum: 25 new words and 25,000 TTS characters per run.
  - It must resume from the next unfinished Oxford word in frequency order.
  - It must run a dry-run and create a backup before generation.
  - It must not deploy Netlify automatically.
- Never exceed the manifest cap.
- Always run `--dry-run` before generation.
- API key is local only:
  `D:\podcast voice\.secrets\google-tts-api-key.txt`
- Never upload or expose the API key in frontend files.

## Important Files

- App UI/data: `deploy-rollback-original\app.js`
- HTML: `deploy-rollback-original\index.html`
- Styles: `deploy-rollback-original\styles.css`
- Audio manifest: `deploy-rollback-original\audio\manifest.json`
- Job Interview jobs:
  `deploy-rollback-original\audio\jobs\job-interview-qanda-days-002-008.json`
- Job builder:
  `deploy-rollback-original\scripts\build-job-interview-audio-jobs.mjs`
- TTS generator:
  `deploy-rollback-original\scripts\generate-tts-batch.mjs`
- Audio files:
  `deploy-rollback-original\audio\words\job-interview-qanda`

## Useful Commands

Run from `D:\podcast voice\deploy-rollback-original`.

Rebuild Job Interview jobs:

```powershell
node scripts\build-job-interview-audio-jobs.mjs
```

Estimate one day:

```powershell
node scripts\generate-tts-batch.mjs --provider google --jobs audio\jobs\job-interview-qanda-days-002-008.json --split-items --spelling on --only-day 2 --dry-run
```

Generate one day:

```powershell
node scripts\generate-tts-batch.mjs --provider google --api-key-file ..\.secrets\google-tts-api-key.txt --jobs audio\jobs\job-interview-qanda-days-002-008.json --split-items --spelling on --only-day 2 --ffmpeg "C:\Users\admin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
```

Generate the no-spelling variant by changing `--spelling on` to `--spelling off`.

Deploy:

```powershell
& 'C:\Users\admin\AppData\Roaming\npm\netlify.cmd' deploy --prod --dir 'D:\podcast voice\deploy-rollback-original' --site a3efdc09-9ec8-4e20-a27e-1f69f554d54b --json
```

Rebuild Reading flashcards data from Podcast:

```powershell
node "D:\podcast voice\daily-english-reader\scripts\build-podcast-flashcards.mjs"
```

Build the combined Learning Hub site for Cloudflare Pages preview/deploy:

```powershell
node "D:\podcast voice\daily-english-reader\scripts\build-learning-hub.mjs"
```

## Verification Completed

- All original 212 Job Interview MP3 files decoded successfully with ffmpeg.
- All 30 Day 2 `english-balanced-v2` files decoded successfully.
- Netlify serves MP3 files with HTTP Range `206`, suitable for iPhone playback.
- Production manifest and Day 2 profile files return HTTP `200`.
- No Google API key was found in deployed frontend files.
- Production `app.js` includes Media Session headset pause and resume handlers.
- Local code now routes MP3 playback through a persistent audio element and does not require new TTS generation.
- Oxford metadata generation completes locally without touching TTS quota.
- Oxford translation generation completed locally into JSON only and did not create any new audio files or consume TTS quota.
- Reading Flashcards local page loads successfully from `http://127.0.0.1:8092/flashcards.html`.
- `podcast-flashcards.json` returns HTTP `200` locally and contains 4,130 cards / 11 categories.
- Combined Learning Hub build completed locally on June 17, 2026.
- Local route checks returned HTTP `200` for:
  `index.html`, `podcast/index.html`, `flashcards.html`, `data/podcast-flashcards.json`, and `podcast/audio/manifest.json`.
- Browser mobile-width sanity check passed for Home, Podcast, and Flashcards. Flashcards loaded 4,130 cards and 12 category filter options including `All podcast categories`.
- JS syntax checks passed for Reading app JS, generated site app JS, Podcast app JS, and both Learning Hub build scripts.
- Daily English Reader unit tests passed: 11/11.
- Local `python -m http.server` returned `200` for an MP3 Range request because it does not emulate Cloudflare/R2 byte-range behavior; verify HTTP `206` again after audio is served from Cloudflare/R2.
- Cloudflare Pages deployment uploaded 316 files and `_headers` successfully.
- Cloudflare Pages route checks returned HTTP `200` for:
  `https://learning-hub-vocabth.pages.dev/`,
  `data/podcast-flashcards.json`, and
  `podcast/audio/manifest.json`.
- Cloudflare Pages MP3 Range check returned `200 OK` with `Accept-Ranges: bytes`, not `206 Partial Content`; move MP3 files to R2 after R2 is enabled, then re-test iPhone playback and headset pause/play.
- Daily Reading automation workflow YAML parsed successfully for both possible repo layouts:
  `D:\podcast voice\.github\workflows\daily-update.yml`
  and
  `D:\podcast voice\daily-english-reader\.github\workflows\daily-update.yml`
- Daily Reading automation verification passed locally:
  JS syntax checks passed and unit tests passed 11/11.
- Reading real-news/audio/POS patch verification passed locally on June 18, 2026:
  Python unit tests passed 15/15.
  Python syntax checks passed for `update_site.py` and `tests/test_update_site.py`.
  JS syntax checks passed for `static/js/app.js` and `scripts/build-learning-hub.mjs`.
- Reading production verification passed on June 18, 2026:
  `content-index.json` shows six stories for `2026-06-18`, split A2 2 / B1 2 / B2 2.
  Production article audio uses `.mp3` with `audio/mpeg` and MP3 `ID3` signature.
  Browser popup verification passed: word `prices` displays `n.` and Thai translation `ราคา`.

## Reading Quality Fix - June 18, 2026

- Deployed via GitHub Actions run:
  `https://github.com/jackyontime1/learning-hub-vocabth/actions/runs/27739671954`
- Production URL:
  `https://learning-hub-vocabth.pages.dev/`
- Production now keeps the latest 7 days: 70 stories total, with 10 stories per day.
- Each day has A1/A2/B1/B2/C1, two stories per level.
- Reading playback uses browser/iPhone Web Speech first for smoother English audio; generated `.wav` files are static fallback placeholders only.
- Reading automation sets `SKIP_AUDIO=1` and no longer installs LibreTranslate/espeak/ffmpeg on GitHub Actions.
- This does not use the Podcast Google Cloud TTS monthly safety cap.
- Production article verification passed:
  `data-reader-text` is present for Web Speech playback,
  vocabulary popups include `data-translation` and `data-pos`,
  article images return HTTP `200`,
  Thai heading/buttons render as real Thai,
  and the detected RSS text typo `2e published` is cleaned.
- Saved Reading words are merged into Flashcards at runtime as category `Saved from Reading` from localStorage key `der.savedWords.v1`.

## Reading Translation Fix - June 18, 2026

- Deployed via GitHub Actions run:
  `https://github.com/jackyontime1/learning-hub-vocabth/actions/runs/27776083108`
- Production URL checked:
  `https://learning-hub-vocabth.pages.dev/news/2026-06-12/rare-footage-captured-of-great-white-shark-in-mediterranean-sea-9407278d/`
- Reading vocabulary now uses Podcast/Oxford flashcard meanings before fallback.
- The popup no longer fabricates labels like `คำว่า filmed`; verified examples:
  `filmed = ถ่ายวิดีโอ`, `diver = นักดำน้ำ`, `shark = ฉลาม`.
- Full Thai translation/summary now uses story-specific title/description/sentence cues instead of only generic category text.
- Production still has 70 stories across the latest 7 days.

## Reading Whole-Article Thai Fix - June 19, 2026

- Deployed via GitHub Actions run:
  `https://github.com/jackyontime1/learning-hub-vocabth/actions/runs/27778492460`
- Production URL checked:
  `https://learning-hub-vocabth.pages.dev/news/2026-06-18/pakistan-ends-luxury-tax-on-menstrual-products-contraceptives-will-price-58e91077/`
- `สรุป/คำแปลไทย` now translates the article content as a whole, starting with the news source and `เนื้อหาข่าวคือ ...`.
- Removed the old word-gloss fallback from the article summary box, so it no longer shows strings like `drop = ...`, `tax = ...`, or `ใจความของประโยคนี้เกี่ยวกับ ...`.
- Production verification passed:
  `schema_version` is `8`,
  glossary-style summary strings are absent,
  `content-index.json` still has 70 stories across 7 days,
  and level distribution remains A1/A2/B1/B2/C1 = 14 each.
- This change did not use Podcast Google Cloud TTS and did not consume the Podcast monthly TTS safety cap.

## Reading Local Full-Translation Pipeline - June 22, 2026

- Prepared a production fix that uses the local/free `facebook/nllb-200-distilled-600M` model for full English-to-Thai article translation.
- The model supports `eng_Latn` to `tha_Thai`, needs no API key, and is licensed CC-BY-NC-4.0 for this personal non-commercial learning project.
- Production now fails safely when a complete Thai translation is unavailable instead of publishing a generic placeholder.
- Translation is generated one sentence at a time so later sentences are not silently omitted.
- Exact curated translations are preserved for known stories, while unseen stories use NLLB plus natural-Thai cleanup.
- Broken source fragments such as `and. Other` and `out of. Reach` are repaired before translation.
- Reading schema is bumped to `9`, forcing all seven retained days to rebuild rather than fixing only today's edition.
- GitHub Actions caches the NLLB model and keeps `SKIP_AUDIO=1`; no Reading MP3, OpenAI API, Google TTS, or Podcast TTS quota is used.
- Verification completed locally:
  - unit tests passed `41/41`;
  - Python/JS syntax and both workflow YAML files passed;
  - dependency resolution dry-run passed;
  - no-audio site dry-run produced 10 stories across A1/A2/B1/B2/C1 and zero MP3 files;
  - a production-like real-news dry-run created a complete schema 9 edition for the expected Toronto date with 10 stories and zero MP3 files;
  - full Thai output is present, but spot checks still show occasional awkward wording and name/entity errors from the free local NLLB model.
- Backup before this change:
  `D:\podcast voice\backups\before-reading-full-thai-v2-20260622-120944.zip`
- Deployment and production browser verification are still pending.

## Reading Reliability and Cover Images - June 23, 2026

- Root cause of the stale June 18 production edition: scheduled runs were queued after the exact 05:00 Toronto guard window, so the build-and-deploy job was skipped.
- The workflow now accepts its timezone-aware scheduled event, manual dispatch, and pushes to `main`; the production job has a 180-minute timeout.
- Production is fail-closed for stale dates, incomplete story counts, wrong A1-C1 distribution, demo content, missing schema 9 Thai text, broken internal links, and exposed secret patterns.
- Cloudflare preview and production are both verified before the rolling cache is committed.
- Image metadata, attribution, relevance reason, duplicate rejection, broken-image rejection, and unique fallback SVGs are implemented.
- `provider-status.json` and `build-report.json` now explain provider attempts, skips, failures, image fallback count, and per-article fallback reasons.
- Production-like dry-run passed for `2026-06-22`: 10 real stories, 2 per A1-C1, schema 9, zero Reading MP3, and 2 unique local image fallbacks.
- Pre-deploy backup:
  `D:\podcast voice\backups\before-daily-reader-reliability-images-20260622-195052.zip`

## Backups

- Full Job Interview Days 1-8:
  `D:\podcast voice\backups\vocabth-job-interview-days1-8-20260611-220500.zip`
- Before Day 2 English balance change:
  `D:\podcast voice\backups\before-day2-english-balance-20260612-105136.zip`
- Before Day 2 `english-balanced-v2` generation:
  `D:\podcast voice\backups\before-day2-english-balanced-v2-20260612-111758.zip`
- Before Day 2 `english-balanced-v2` deploy:
  `D:\podcast voice\backups\before-deploy-day2-english-balanced-v2-20260612-112218.zip`
- Before Oxford redistribution:
  `D:\podcast voice\backups\before-oxford-redistribute-20260612-124030.zip`
- Before Oxford natural-Thai translation deploy attempt:
  `D:\podcast voice\backups\before-oxford-natural-thai-deploy-20260612-145952.zip`
- Before Learning Hub Pages/R2 combined build:
  `D:\podcast voice\backups\before-learning-hub-pages-r2-20260617-112609.zip`
- Before Cloudflare Pages deploy:
  `D:\podcast voice\backups\before-cloudflare-pages-deploy-20260617-114149.zip`
- Before Daily Reader Cloudflare automation changes:
  `D:\podcast voice\backups\before-daily-reader-cloudflare-auto-20260617-120401.zip`
- Before real RSS Reading deploy:
  `D:\podcast voice\backups\before-real-rss-reading-deploy-20260617-204634.zip`
- Before Reading real-news audio/POS deploy:
  `D:\podcast voice\backups\before-reading-real-news-audio-pos-deploy-20260618-104819.zip`
- Before Reading quality fix:
  `D:\podcast voice\backups\before-reading-quality-fix-20260618-114424.zip`
- Before Reading translation fix:
  `D:\podcast voice\backups\before-reading-translation-fix-20260618-translation-fix.zip`
- Before Reading whole-article Thai fix:
  `D:\podcast voice\backups\before-20260619-reading-whole-thai-translation.zip`
- Before Reading local full-translation pipeline:
  `D:\podcast voice\backups\before-reading-full-thai-v2-20260622-120944.zip`
- Before Daily Reader reliability and cover-image work:
  `D:\podcast voice\backups\before-daily-reader-reliability-images-20260622-195052.zip`

## Next Action

1. Monitor the next scheduled Daily Reader run after commit
   `d104c978b6146fcbf8fbcf3f50fd98020ee65ebf`.
2. If that scheduled run passes, start Round 2B: Reading UI/UX polish.
3. Keep Round 2B focused on:
   - Article-page readability
   - Thai translation box
   - Useful-phrases presentation
   - Reducing visual clutter from word highlighting
   - Mobile layout
   - Saved vocabulary and saved-story polish later
4. Preserve the free-only production constraints documented above.

Keep responses and progress updates concise to reduce token use.
