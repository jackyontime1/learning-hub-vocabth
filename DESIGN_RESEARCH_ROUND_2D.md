# Round 2D-A: Learning UI / UX Redesign Research

Date: 2026-07-01
Project: Reading BBC / Daily English Reader / Learning Hub
Phase: Round 2D-A research and design direction only
Production audited: https://learning-hub-vocabth.pages.dev/

## Executive Summary

The current interface is functional, responsive, and recognizably a learning
tool, but its visual structure still behaves like a dashboard. A large image-led
hero, repeated bordered panels, nested cards, small utility text, and many
simultaneous controls compete with the reading task.

The recommended direction is a **quiet bilingual reader**: English prose is the
primary surface; Thai translation, useful phrases, pronunciation, saving, and
audio remain nearby but visually secondary until needed. The existing restrained
blue identity, static architecture, schema 10 content, and free-only constraints
should remain. Round 2D-B should not be a wholesale redesign. It should first
improve the article reading flow, vocabulary popup, and mobile comfort. Homepage
and story-card restructuring should follow only after that reading flow is
verified.

### Verified Baseline

- Production loaded successfully at desktop and 390 x 844 mobile viewports.
- No horizontal overflow was observed at 390px.
- No browser console warnings or errors were observed during the audit.
- The word popup remained inside the 390px viewport in the tested case.
- The article reading size was 19px with approximately 1.85 line height on mobile.
- The homepage and article page retain schema-10 learning features: CEFR level,
  full Thai translation, useful phrases, word lookup, optional IPA, audio, and
  saved vocabulary.
- This round did not change production code, schema, workflow, or generated data.

## Audit Method

The audit combined:

1. Source inspection of the current templates, CSS, and popup JavaScript.
2. Review of existing `PRODUCT.md` and `DESIGN.md` constraints.
3. Production browser checks on the homepage and an A1 article.
4. Desktop and 390 x 844 mobile screenshots.
5. Mobile overflow, type-size, popup-boundary, and console checks.
6. Reference research using official or first-party sources where possible.

No external design assets, code, fonts, or paid services are proposed.

## Audit Health Score

| Dimension | Score | Key finding |
| --- | ---: | --- |
| Accessibility | 2/4 | Core semantics exist, but tiny labels, small controls, missing language metadata, and incomplete popup focus behavior need work. |
| Performance | 3/4 | The static site is lean and images lazy-load in lists; the oversized image-led first viewport and external icon dependency are remaining costs. |
| Responsive design | 3/4 | The tested 390px pages did not overflow, but six-item mobile navigation and several controls are too small for comfortable repeated use. |
| Theming | 3/4 | Useful tokens exist, but many hard-coded colors and several competing semantic accents weaken consistency. |
| Anti-patterns | 2/4 | No gradients or glassmorphism, but the large hero, repeated cards, nested panels, and badge-heavy hierarchy still suggest a generic dashboard. |
| **Total** | **13/20** | **Acceptable; focused reading-flow work is needed before broad polish.** |

### Anti-pattern Verdict

The current site is not an "AI slop gallery," but it does not yet feel like a
fully resolved reading product. The strongest generic-AI/product-template tells
are the full-width dark hero, repeated white cards with borders and shadows,
card-within-card section structure, tiny metadata, and multiple colored badges.
The right correction is subtraction and hierarchy, not a new visual theme.

## Research References

References are used for principles only. No brand, content, proprietary data, or
visual asset should be copied.

| Reference | Useful idea | What not to copy | Relevance |
| --- | --- | --- | --- |
| [Readlang](https://readlang.com/) | Click a word in context, see a translation immediately, and save it for later review. Learning help stays attached to reading. | Paid/AI features, its branding, or an interface that highlights too many words at once. | Strong model for the shortest path from reading to meaning to review. |
| [LingQ](https://www.lingq.com/) | Combine authentic reading, audio, contextual vocabulary, and progress without leaving the lesson. | Dense word-state coloring, metrics-heavy gamification, paid architecture, or broad content-library complexity. | Confirms that reading, listening, and vocabulary should form one flow. |
| [Cambridge English-Thai Dictionary](https://dictionary.cambridge.org/dictionary/english-thai/) | Present word, part of speech, pronunciation, Thai meaning, and usage examples in a clear lexical hierarchy. | Cambridge branding, dictionary content, layouts, or licensed data. | Best reference for making the popup feel like a trustworthy dictionary rather than a game card. |
| [GOV.UK focus states](https://design-system.service.gov.uk/get-started/focus-states/) | Make keyboard focus unambiguous on light and colored surfaces using a consistent, high-contrast treatment. | The yellow/black visual identity itself. | Supports a visible cross-site focus system without adding decoration. |
| [W3C WCAG 2.2 Understanding](https://www.w3.org/WAI/WCAG22/Understanding/) | Use measurable checks for reflow, focus visibility, focus not obscured, keyboard access, and minimum target size. | Treating minimum compliance as the complete design goal. | Provides the acceptance criteria for mobile, popup, and keyboard behavior. |
| [Apple typography guidance](https://developer.apple.com/design/human-interface-guidelines/typography) | Favor legible default sizes, a stable hierarchy, adaptable layouts, and minimal typeface mixing. | Native-iOS styling, Apple branding, or platform-specific components. | Useful because many learners will read long bilingual passages on phones. |

### Reference Conclusion

The strongest shared principle is **in-context support with minimal interruption**.
Readlang and LingQ validate the workflow; Cambridge validates the lexical
hierarchy; GOV.UK, W3C, and Apple provide accessibility and mobile legibility
guardrails. The project can apply these principles entirely with local HTML,
CSS, and JavaScript.

## Design Principles

1. **Reading is the product.** The article must begin sooner than supporting
   metadata, imagery, disclaimers, or utilities.
2. **English first, Thai close by.** Thai support should be easy to reveal and
   comfortable to read without visually competing with the English prose.
3. **One interaction language.** Blue means actionable or selected. CEFR colors
   identify level only. Green means success or translation support only.
4. **Help appears in context.** Word meaning, IPA, speech, and save state should
   appear near the selected word and disappear cleanly.
5. **Quiet does not mean tiny.** Reduce decoration while keeping body text,
   controls, focus states, and labels comfortably visible.
6. **Flat before floating.** Use rules, spacing, and tonal sections before cards
   and shadows. Reserve elevation for the vocabulary popup.
7. **Mobile is the primary reading constraint.** A learner should reach the
   article quickly, read without horizontal movement, and operate controls with
   one hand.
8. **No fabricated polish.** Missing IPA or translation metadata stays hidden or
   truthfully unavailable. UI styling must never imply data that does not exist.

## Recommended Design Direction

### Direction: The Quiet Bilingual Reader

The interface should resemble a dependable reading workspace in daylight, not a
news portal hero or a startup dashboard. Use a clear white reading surface,
cool-neutral page background, dark ink, restrained blue actions, and small CEFR
accents. Images support orientation but do not dominate the learning task.

The homepage should answer three questions quickly:

1. What can I read today?
2. Which level is right for me?
3. Is this a practice story or real news?

The article page should answer three more:

1. Where does the English reading begin?
2. How do I check a word without losing my place?
3. Where are the full Thai translation and useful phrases?

### Deliberate Non-directions

- No purple/blue gradients, glow, glassmorphism, or ambient blobs.
- No oversized marketing hero.
- No card around every section and no cards nested inside cards.
- No streaks, points, confetti, or gamified vocabulary popup.
- No frontend framework or component-library migration.
- No new font dependency in Round 2D-B.
- No changes to schema 10, content generation, IPA generation, or deployment.

## Current UI Audit

### Homepage / Today Page

| Severity | Issue | Why it hurts learning | Fix direction | Round |
| --- | --- | --- | --- | --- |
| High | The 465-500px image hero dominates the first viewport. | Learners see a news-style promotion before they see the level-based reading path; on mobile, one story consumes most of the screen. | Replace the full-bleed hero with a compact Today introduction or restrained featured row that exposes level choices immediately. | 2D-C after reading flow |
| High | Weak or fallback imagery is enlarged into the primary brand signal. | Image relevance varies, so the interface can look accidental and title contrast depends on the image. | Treat imagery as supporting media with a stable aspect ratio and a light content-first layout. | 2D-C |
| Medium | Sidebar filters plus repeated level sections create dashboard density. | Users must parse dates, categories, levels, status, hero, and cards before choosing a reading. | Make level the primary path; move category and date to quieter secondary controls. | 2D-C |
| Medium | Practice-story disclaimers repeat inside every A1/A2 card. | Repetition adds visual weight and pushes useful story information down. | Keep a concise, explicit content-type label on each story and explain the distinction once per level/section. | 2D-C |
| Low | The decorative profile circle has no function. | A familiar account affordance implies a feature that does not exist. | Remove it or reserve the space for a real action only when one exists. | 2D-C |

### Article Reading Page

| Severity | Issue | Why it hurts learning | Fix direction | Round |
| --- | --- | --- | --- | --- |
| High | On mobile, a 480px hero plus disclaimer, attribution, and metadata delays the reading body. | Learners must scroll through more than one screen before reaching the lesson. | Compress the hero into a compact article header; keep classification and source visible without making the image primary. | 2D-B |
| High | Every word has a dotted underline. | Continuous decoration fragments sentence rhythm and makes sustained reading resemble a form or annotated worksheet. | Remove persistent underlines; preserve discoverability with a short instruction, pointer cursor, hover/focus state, and selected-word state. | 2D-B |
| Medium | The reading toolbar, audio player, translate control, and font controls form several stacked utility bands. | Controls visually outweigh a short A1 story and interrupt the move into prose. | Consolidate controls into one quiet utility row that wraps predictably on mobile. | 2D-B |
| Medium | Article sections are nested inside a bordered reader card. | Translation and phrase panels read as cards inside a card, increasing visual noise. | Let the reading surface be unframed or singly framed; separate sections with spacing and rules. | 2D-B |
| Low | Fixed "5 min read" is not credible for very short A1 stories. | An obviously inaccurate estimate weakens trust. | Calculate or omit reading time in a later content/metadata task; do not change schema in UI work. | Later |

### Word Popup / Vocabulary Interaction

| Severity | Issue | Why it hurts learning | Fix direction | Round |
| --- | --- | --- | --- | --- |
| High | `role="dialog"` is used without moving focus into the popup, trapping it, or restoring it on close. | Keyboard and assistive-technology behavior does not match the announced dialog model. | Choose a deliberate non-modal popover pattern or implement complete dialog focus behavior; restore focus to the selected word. | 2D-B |
| Medium | The large green/yellow split action footer feels game-like. | It competes with word, IPA, and Thai meaning, weakening dictionary hierarchy. | Use neutral secondary actions with one clear selected/saved state; keep the lexical content dominant. | 2D-B |
| Medium | Missing translation is displayed with the same visual prominence as a valid meaning. | Learners may mistake an unavailable meaning for useful dictionary content. | Keep truthful unavailable copy but style it as a quiet status, not the primary definition. | 2D-B |
| Positive | The tested popup stayed inside the 390px viewport and optional IPA hides safely. | The current positioning and fail-safe behavior provide a sound base. | Preserve these behaviors and add regression checks. | Preserve |

### Thai Translation

| Severity | Issue | Why it hurts learning | Fix direction | Round |
| --- | --- | --- | --- | --- |
| Medium | Thai translation is a bordered green card inside the reader container. | The full translation feels like an add-on rather than a natural second reading layer. | Use a quiet full-width tonal section with a clear heading, comfortable Thai type, and no nested-card effect. | 2D-B |
| Medium | Thai text lacks explicit `lang="th"` metadata. | Screen readers and pronunciation tools may use the wrong language rules. | Add language attributes to Thai headings, translations, disclaimers, and meanings where practical. | 2D-B |
| Positive | The label “แปลไทยทั้งบท” clearly distinguishes full translation from summary. | The content promise is unambiguous. | Preserve the wording. | Preserve |

### Useful Phrases

| Severity | Issue | Why it hurts learning | Fix direction | Round |
| --- | --- | --- | --- | --- |
| Medium | The phrase area becomes a large tinted panel, especially for short A1 stories on desktop. | The container has more visual mass than its content and disrupts vertical rhythm. | Use a compact ruled list with English phrase, Thai meaning, and source sentence in a stable three-line hierarchy. | 2D-B |
| Medium | Source sentences use small muted text. | Context is essential learning material, not disposable metadata. | Increase size/contrast and visually label context without uppercase microcopy. | 2D-B |
| Positive | Three to five source-matched phrases provide a strong, repeatable learning unit. | The content model already supports a valuable post-reading step. | Preserve all schema and validation behavior. | Preserve |

### Level / Story Cards

| Severity | Issue | Why it hurts learning | Fix direction | Round |
| --- | --- | --- | --- | --- |
| High | Story excerpts are 12px muted serif text. | Core decision-making content is difficult to scan, particularly on phones and lower-quality displays. | Use at least 15-16px for meaningful summaries and reserve 12-13px for true metadata. | 2D-C |
| Medium | Cards sit inside bordered level/date panels, producing nested containers. | Repeated boundaries make every item equally loud and reinforce the dashboard feeling. | Use one level section with simple story rows or minimally framed cards, not both. | 2D-C |
| Medium | Five CEFR colors plus separate category/action colors create many competing cues. | Learners must decode decoration instead of using a consistent level system. | Keep CEFR color to compact level markers; use neutral text for category and metadata. | 2D-C |

### Mobile Layout

| Severity | Issue | Why it hurts learning | Fix direction | Round |
| --- | --- | --- | --- | --- |
| High | Six bottom-navigation labels render at 9px. | Labels are difficult to read and the bar feels crowded despite adequate overall height. | Prioritize the core destinations, use at least 11-12px labels, and test long English labels without overlap. | 2D-B navigation polish or 2D-C IA |
| Medium | Several controls are 30-38px high. | Repeated use is less comfortable than a 40-44px mobile target standard. | Raise primary reading controls to 44px where practical; verify spacing and target-size exceptions. | 2D-B |
| Positive | The tested homepage and article had no horizontal overflow at 390px. | Existing breakpoints and width constraints are structurally sound. | Preserve and test at 320, 390, 768, and desktop widths. | Preserve |

### Typography

| Severity | Issue | Why it hurts learning | Fix direction | Round |
| --- | --- | --- | --- | --- |
| High | Important labels and summaries frequently use 9-12px type. | The product is for sustained language study; tiny supporting text increases effort and weakens hierarchy. | Set a 13px metadata floor and a 15-16px meaningful-content floor. | 2D-B/2D-C |
| Positive | Article prose uses a 19-20px serif with generous line height and a 72ch limit. | This supports sustained English reading and already matches the intended editorial direction. | Preserve, then test font scaling and Thai pairing. | Preserve |

### Spacing

| Severity | Issue | Why it hurts learning | Fix direction | Round |
| --- | --- | --- | --- | --- |
| Medium | The system alternates between very large hero space and dense 3-10px utility spacing. | Rhythm feels assembled from components rather than designed around a reading sequence. | Use a consistent 4/8/12/16/24/32/48 scale and reserve 32-48px gaps for major learning sections. | 2D-B/2D-C |
| Medium | Repeated panel padding and borders create visual pauses before every section. | Too many stops interrupt reading flow. | Prefer section spacing and a single divider over another container. | 2D-B |

### Color and Accessibility

| Severity | Issue | Why it hurts learning | Fix direction | Round |
| --- | --- | --- | --- | --- |
| High | There is no consistent site-wide authored `:focus-visible` treatment for all links, buttons, and selects. | Browser defaults vary, and focus can be difficult to track across white, tinted, and image surfaces. | Add one high-contrast 2-3px focus system and preserve specialized word/popup focus states. | 2D-B |
| Medium | Hard-coded colors sit beside tokens and podcast purple has a separate interaction vocabulary. | Similar states can look unrelated and maintenance becomes error-prone. | Consolidate interaction/state tokens; keep product-area color as a small identity cue, not a different control system. | 2D-C |
| Positive | Primary ink, white surfaces, restrained blue actions, and the absence of gradients/glass are appropriate. | The base palette can support the redesign without rebranding. | Preserve the palette and reduce how many colors appear simultaneously. | Preserve |

## Proposed Visual System

This system refines the existing `DESIGN.md`; it does not require a dependency or
framework change.

### Typography Scale

| Role | Desktop | Mobile | Notes |
| --- | --- | --- | --- |
| Page title | 32px / 1.2 / 700 | 26px / 1.2 / 700 | Use only for real page titles. |
| Section title | 22px / 1.3 / 700 | 20px / 1.3 / 700 | Level and learning-section headings. |
| Card/story title | 18px / 1.35 / 700 | 18px / 1.35 / 700 | Allow wrapping; no truncation by default. |
| English reading | 20px / 1.8 | 19px / 1.8 | Keep the existing serif stack and 65-72ch measure. |
| Thai reading | 17px / 1.9 | 17px / 1.9 | Use the Thai-capable sans stack and `lang="th"`. |
| Interface body | 16px / 1.5 | 16px / 1.5 | Controls and explanatory text. |
| Metadata floor | 13px / 1.45 | 13px / 1.45 | Avoid essential text below this size. |

Do not introduce fluid viewport-based type. Keep fixed responsive steps so labels
and controls remain predictable.

### Spacing Scale

Use `4, 8, 12, 16, 24, 32, 48px`.

- 4-8px: icon/label and tight metadata relationships.
- 12-16px: control groups and component padding.
- 24px: related content blocks.
- 32-48px: transitions between article, translation, phrases, and review.

### Color Direction

- Page: cool neutral near-white, preserving the existing `--paper` direction.
- Reading surface: white.
- Primary ink: existing dark navy ink.
- Supporting ink: dark enough for normal-size WCAG AA text.
- Action/focus: existing clear blue.
- Thai support: very light green tint, used as a section background only.
- CEFR accents: small semantic markers only: A1 green, A2 teal-green, B1 blue,
  B2 amber, C1 plum.
- Error, warning, and success colors must not double as decorative level colors.

### Cards and Sections

- Maximum radius: 8px for reading panels; 6-8px for story cards.
- Use either a border or a compact shadow, never both as decoration.
- Article, translation, and useful phrases should read as one vertical document,
  separated by spacing and rules.
- Story collections may use repeated cards, but the parent section should not also
  look like a card.

### Buttons

- 44px mobile target for primary reading actions; 40px desktop minimum.
- 5-7px radius, direct labels, stable dimensions, no oversized pills.
- Use familiar icons only where they improve recognition.
- Primary blue for the main action; neutral outlined/quiet buttons for secondary
  actions; semantic color only after a real state change.

### CEFR Badges

- Compact rounded rectangle, not a pill.
- Always include the level text; never rely on color alone.
- Use the color on the badge only, not across the whole story card.
- Add the reading-type label in plain text where needed: Practice Story, Easy
  News, Real News, or Advanced News.

### Vocabulary Popup

- Keep it anchored and viewport-bounded where possible.
- Lexical order: word, part of speech and IPA, Thai meaning/status, speech, save
  state.
- White surface, 8px radius, one compact shadow, and neutral action row.
- Preserve 44px close/speech controls.
- Decide and implement one accessible interaction model: non-modal popover or
  full dialog behavior, not a mixture.
- Restore focus to the selected word after closing.

### Thai Translation Block

- Full-width quiet green-tint section within the article flow.
- Heading remains “แปลไทยทั้งบท”.
- Thai body uses 17px/1.9 and `lang="th"`.
- No nested card shadow; one boundary or tonal change is enough.

### Useful Phrases Block

- Use a simple ruled list rather than separate cards.
- English phrase at 16-17px semibold.
- Thai meaning at 16px with `lang="th"`.
- Source sentence at 14-15px with adequate contrast.
- Keep all three to five validated phrases visible.

### Breakpoints

- Keep the current structural breakpoints near 760px and 1050px to minimize risk.
- Add checks rather than additional breakpoints unless a verified layout failure
  requires one.
- Required preview widths: 320, 390, 768, 1024, and 1280px.

## Recommended Round 2D-B Scope

### Scope Recommendation

Round 2D-B should implement **the core reading flow only**:

1. Article header and reading-page hierarchy.
2. Word interaction and popup visual/accessibility polish.
3. Thai translation and useful-phrase presentation.
4. Mobile reading controls, focus states, and touch targets.

Homepage information architecture and story-card redesign should be Round 2D-C.
Combining both surfaces in one commit would enlarge the browser-test matrix and
make regressions harder to isolate.

### A. Article Reading Page Readability

- Likely files: `templates/article.html`, `static/css/styles.css`.
- Change: shorten the image/header footprint, bring the lesson above the fold,
  simplify nested containers, and remove persistent dotted decoration from every
  word.
- Risk: Medium. Template structure and responsive CSS change, but no data model
  change is required.
- Checks: template assertions, article rendering, heading order, full Thai and
  useful-phrase presence, no schema regression.
- Browser preview: required on A1 and C1 articles.
- Mobile check: required at 320 and 390px.

### B. Homepage / Today Learning Path

- Recommendation: defer structural implementation to Round 2D-C.
- Likely files: `templates/index.html`, `templates/daily.html`,
  `static/css/styles.css`, possibly existing filter JavaScript only.
- Planned direction: compact Today header, level-first choice, quieter date and
  category filtering, and less disclaimer repetition.
- Risk: Medium-high because homepage filters and day/level visibility are coupled
  to existing JavaScript.
- Browser preview: required for every filter combination and empty state.
- Mobile check: required at 320, 390, and 768px.

### C. Word Popup Visual Polish

- Likely files: `templates/article.html`, `static/css/styles.css`,
  `static/js/app.js`.
- Change: establish a dictionary hierarchy, neutralize the action footer, choose
  correct popover/dialog semantics, and restore focus on close.
- Risk: Medium because pointer, keyboard, touch, and resize behavior intersect.
- Checks: JavaScript syntax, targeted popup tests if available, Escape/close/focus
  behavior, optional IPA hidden, missing meaning truthful, save state preserved.
- Browser preview: required with supported and unsupported IPA words.
- Mobile check: popup must remain inside 320 and 390px viewports.

### D. Level / Story Cards

- Recommendation: defer structural implementation to Round 2D-C.
- Likely files: `templates/index.html`, `templates/daily.html`,
  `static/css/styles.css`.
- Planned direction: remove nested panel/card treatment, increase summary text,
  and restrict CEFR color to the level marker.
- Risk: Low-medium after homepage path is approved.
- Browser preview: required for long titles, fallback images, and practice labels.
- Mobile check: one-column cards with no clipped titles or controls.

### E. Mobile Reading Comfort

- Likely files: `templates/article.html`, `templates/base.html` only if navigation
  semantics require it, `static/css/styles.css`, `static/js/app.js` for popup focus.
- Change: expose reading sooner, enlarge recurring controls, maintain bottom-nav
  clearance, and add consistent focus-visible styling.
- Risk: Medium. Navigation changes should remain visual in 2D-B; information
  architecture changes should wait for 2D-C.
- Checks: 320/390px overflow, text zoom, bottom-nav occlusion, popup bounds,
  keyboard focus, and console errors.
- Browser preview: mandatory.

### Files Likely Affected in Round 2D-B

- `daily-english-reader/templates/article.html`
- `daily-english-reader/static/css/styles.css`
- `daily-english-reader/static/js/app.js`
- `daily-english-reader/tests/test_update_site.py` for focused render/template
  regression checks only

`update_site.py`, schema files, workflows, IPA data, and generated production data
should not change unless a separately approved blocker proves that unavoidable.

## Round 2D-B Risks

1. Removing persistent word underlines may reduce discoverability unless the
   instruction, hover/focus state, and selected state remain clear.
2. Popup semantics can regress keyboard or touch behavior if visual and
   accessibility changes are separated.
3. Reducing the hero must preserve source, story type, CEFR level, date, and
   fictional-story disclosure.
4. Mobile bottom navigation may obscure the final controls or focused element.
5. Thai line height and English serif metrics differ; both languages need visual
   checks with short A1 and long C1 content.
6. Existing generated pages may cache CSS; asset versioning and production
   verification must remain unchanged unless explicitly approved.
7. Browser screenshots covered representative pages, not every article/image
   combination.

## Round 2D-B Success Criteria

- No horizontal overflow at 320px or 390px.
- The English article begins within the first practical mobile reading screen
  after a compact, truthful article header.
- English prose remains 19-20px with approximately 1.8 line height and a 65-72ch
  desktop measure.
- Thai translation remains complete, visibly labeled “แปลไทยทั้งบท”, and uses
  readable Thai typography.
- All three to five useful phrases remain visible with English, Thai, kind, and
  source context.
- Word popup remains fully inside the viewport at 320, 390, 768, and desktop
  widths.
- Popup opens by pointer and keyboard, closes with Escape and its close button,
  and returns focus to the selected word.
- Optional IPA appears when available and remains hidden safely when missing.
- Missing meanings remain truthful and are not styled as valid translations.
- Repeated mobile controls meet a 44px target where practical; no essential label
  is below 11-12px and meaningful content is not below 15px.
- Focus states are visible on links, buttons, selects, word tokens, and popup
  controls.
- No browser console errors.
- Existing save, speech, font-size, translation-toggle, and audio behavior still
  works.
- No schema/content regression and production verification remains unchanged.
- CSS and template diffs stay scoped to the reading flow.
- No new frontend dependency, framework, font service, paid API, or build step.
- Page loading remains fast and list images retain lazy loading.

## Verification Plan for Round 2D-B

1. Run targeted template/render tests first.
2. Run `python -m py_compile` for touched Python tests or render code only.
3. Run the existing Daily Reader unit suite from `daily-english-reader`.
4. Run `node --check static/js/app.js`.
5. Run `git diff --check` on approved files.
6. Preview representative A1 and C1 pages at 320, 390, 768, and 1280px.
7. Check keyboard navigation, popup focus return, Escape, speech-button fallback,
   translation toggle, saved-word state, and console errors.
8. Confirm no generated data, workflow, schema, IPA, or protected file changed.

## Recommended Model for Next Step

Use **gpt-5.5 High** for the focused Round 2D-B implementation. Escalate to Extra
High only if popup accessibility requires an architectural interaction change or
browser verification reveals a non-obvious regression.

## Owner Approval Question

Approve Round 2D-B as a focused article-reading implementation covering only the
article header, reading surface, Thai translation, useful phrases, vocabulary
popup, focus states, and mobile reading comfort, while deferring homepage and
story-card restructuring to Round 2D-C?
