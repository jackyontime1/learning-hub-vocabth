const ARTICLE_KEY = "der.savedArticles.v1";
const WORD_KEY = "der.savedWords.v1";
const PREF_KEY = "der.preferences.v1";
const FLASHCARD_KEY = "learnhub.flashcards.v1";

function readObject(key, fallback = {}) {
  try { return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback)); }
  catch { return fallback; }
}

function writeObject(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function migrateStorage() {
  if (!localStorage.getItem(ARTICLE_KEY)) {
    const legacy = readObject("daily-english-reader-stars", []);
    writeObject(ARTICLE_KEY, Object.fromEntries((Array.isArray(legacy) ? legacy : []).map((id) => [id, { id }])));
  }
  if (!localStorage.getItem(WORD_KEY)) {
    const legacy = readObject("daily-english-reader-words", []);
    writeObject(WORD_KEY, Object.fromEntries((Array.isArray(legacy) ? legacy : []).map((word) => [word, { word }])));
  }
}

migrateStorage();
let savedArticles = readObject(ARTICLE_KEY);
let savedWords = readObject(WORD_KEY);
let preferences = readObject(PREF_KEY, { speed: 1, fontScale: 1 });
let flashcardProgress = readObject(FLASHCARD_KEY);
let flashcardDeck = { data: null, cards: [], index: 0, revealed: false };
let flashcardAudio = null;
let storySpeech = { utterance: null, words: [], index: 0, timer: null, startedAt: 0, elapsed: 0, duration: 0, playing: false };
let activeWord = null;
let activeWordTarget = null;
let homeFilters = { date: "", category: "all", level: "all" };

function articleFromButton(button) {
  return {
    id: button.dataset.id,
    title: button.dataset.title,
    url: button.dataset.url,
    level: button.dataset.level,
    category: button.dataset.category,
    date: button.dataset.date,
    image: button.dataset.image,
    savedAt: new Date().toISOString(),
  };
}

function refreshArticleButtons() {
  document.querySelectorAll("[data-save-article]").forEach((button) => {
    const active = Boolean(savedArticles[button.dataset.id]);
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
    const label = button.querySelector("span");
    if (label) label.textContent = active ? "Saved" : "Save";
    const icon = button.querySelector("i");
    if (icon) icon.className = active ? "fa-solid fa-bookmark" : "fa-regular fa-bookmark";
  });
}

function speakWord(word) {
  if (!word || !("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(word);
  utterance.lang = "en-US";
  utterance.rate = 0.82;
  speechSynthesis.speak(utterance);
}

function storySpeechSupported() {
  return "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
}

function storyWords(audio) {
  const readerText = (audio?.dataset.readerText || "")
    .trim()
    .replace(/\n\s*\n/g, " ... ")
    .replace(/\s+/g, " ");
  return readerText.split(" ").filter(Boolean);
}

function storyRate() {
  const speed = Number(preferences.speed || 1);
  return Math.max(0.75, Math.min(1.25, speed));
}

function stopStorySpeech(reset = false) {
  if (storySpeech.timer) window.clearInterval(storySpeech.timer);
  storySpeech.timer = null;
  if (storySpeechSupported()) speechSynthesis.cancel();
  storySpeech.playing = false;
  if (reset) {
    storySpeech.index = 0;
    storySpeech.elapsed = 0;
  }
}

function updateStorySpeechProgress() {
  const current = document.querySelector("#audioCurrent");
  const duration = document.querySelector("#audioDuration");
  const progress = document.querySelector("#audioProgress");
  if (!current || !duration || !progress) return;
  const elapsed = storySpeech.playing
    ? storySpeech.elapsed + ((Date.now() - storySpeech.startedAt) / 1000)
    : storySpeech.elapsed;
  current.textContent = formatTime(Math.min(elapsed, storySpeech.duration || 0));
  duration.textContent = formatTime(storySpeech.duration || 0);
  progress.value = storySpeech.duration ? String((elapsed / storySpeech.duration) * 100) : "0";
}

function playStorySpeech(audio, toggle) {
  if (!storySpeechSupported()) return false;
  const words = storyWords(audio);
  if (!words.length) return false;
  const text = words.slice(storySpeech.index).join(" ");
  if (!text) {
    storySpeech.index = 0;
    return playStorySpeech(audio, toggle);
  }
  if (!storySpeech.duration) storySpeech.duration = Math.max(8, words.length / (2.35 * storyRate()));
  storySpeech.words = words;
  const startIndex = storySpeech.index;
  storySpeech.utterance = new SpeechSynthesisUtterance(text);
  storySpeech.utterance.lang = "en-US";
  storySpeech.utterance.rate = storyRate();
  storySpeech.utterance.pitch = 1;
  storySpeech.utterance.onboundary = (event) => {
    if (event.name === "word" || event.charIndex >= 0) {
      const spoken = text.slice(0, event.charIndex).trim().split(/\s+/).filter(Boolean).length;
      storySpeech.index = Math.min(words.length, startIndex + spoken);
    }
  };
  storySpeech.utterance.onend = () => {
    stopStorySpeech(false);
    storySpeech.index = 0;
    storySpeech.elapsed = 0;
    updateStorySpeechProgress();
    if (toggle) toggle.querySelector("i").className = "fa-solid fa-play";
  };
  storySpeech.utterance.onerror = () => {
    stopStorySpeech(false);
    if (toggle) toggle.querySelector("i").className = "fa-solid fa-play";
  };
  storySpeech.startedAt = Date.now();
  storySpeech.playing = true;
  storySpeech.timer = window.setInterval(updateStorySpeechProgress, 250);
  speechSynthesis.cancel();
  speechSynthesis.speak(storySpeech.utterance);
  if (toggle) toggle.querySelector("i").className = "fa-solid fa-pause";
  return true;
}

function pauseStorySpeech(toggle) {
  if (!storySpeech.playing) return false;
  storySpeech.elapsed += (Date.now() - storySpeech.startedAt) / 1000;
  stopStorySpeech(false);
  updateStorySpeechProgress();
  if (toggle) toggle.querySelector("i").className = "fa-solid fa-play";
  return true;
}

function positionPopover(target) {
  const popover = document.querySelector("#vocabPopover");
  if (!popover) return;
  popover.hidden = false;
  const rect = target.getBoundingClientRect();
  const width = popover.offsetWidth;
  const height = popover.offsetHeight;
  const margin = 12;
  const left = Math.max(margin, Math.min(innerWidth - width - margin, rect.left + rect.width / 2 - width / 2));
  let top = rect.top - height - 12;
  if (top < margin) top = rect.bottom + 12;
  popover.style.left = `${left}px`;
  popover.style.top = `${top}px`;
}

function openWord(target) {
  activeWordTarget = target;
  activeWord = {
    word: target.dataset.word,
    pos: target.dataset.pos || "",
    translation: target.dataset.translation || "ยังไม่มีคำแปล",
    articleId: document.querySelector(".reader")?.dataset.articleId || "",
    articleTitle: document.querySelector(".article-hero h1")?.textContent || "",
    savedAt: new Date().toISOString(),
  };
  document.querySelector("#popoverWord").textContent = activeWord.word;
  document.querySelector("#popoverPronunciation").textContent = `${activeWord.pos ? `${activeWord.pos} · ` : ""}English: ${activeWord.word.toLowerCase()}`;
  document.querySelector("#popoverTranslation").textContent = activeWord.translation;
  document.querySelector("#learnWord").classList.toggle("active", Boolean(savedWords[activeWord.word.toLowerCase()]));
  positionPopover(target);
}

function renderArticleSavedWords() {
  const container = document.querySelector("#articleSavedWords");
  if (!container) return;
  const articleId = document.querySelector(".reader")?.dataset.articleId;
  const rows = Object.values(savedWords).filter((row) => row.articleId === articleId);
  container.innerHTML = rows.length ? rows.map((row) => `
    <div class="saved-word-row">
      <button data-speak="${escapeHtml(row.word)}" type="button"><i class="fa-solid fa-volume-high"></i></button>
      <span><strong>${escapeHtml(row.word)}${row.pos ? ` <em>${escapeHtml(row.pos)}</em>` : ""}</strong><small>${escapeHtml(row.translation || "")}</small></span>
      <button data-remove-word="${escapeHtml(row.word.toLowerCase())}" type="button" aria-label="Remove ${escapeHtml(row.word)}"><i class="fa-solid fa-xmark"></i></button>
    </div>`).join("") : `<p class="inline-empty">Select a word and press “เรียน” to save it here.</p>`;
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  })[character]);
}

function renderVocabularyPage(filter = "") {
  const container = document.querySelector("#savedWordList");
  if (!container) return;
  const rows = Object.values(savedWords).filter((row) =>
    `${row.word || ""} ${row.translation || ""}`.toLowerCase().includes(filter.toLowerCase())
  );
  container.innerHTML = rows.map((row) => `
    <article class="saved-word-card">
      <button data-speak="${escapeHtml(row.word)}" type="button"><i class="fa-solid fa-volume-high"></i></button>
      <div><h2>${escapeHtml(row.word)}${row.pos ? ` <em>${escapeHtml(row.pos)}</em>` : ""}</h2><p>${escapeHtml(row.translation || "")}</p><small>${escapeHtml(row.articleTitle || "")}</small></div>
      <button data-remove-word="${escapeHtml((row.word || "").toLowerCase())}" type="button" aria-label="Remove word"><i class="fa-regular fa-trash-can"></i></button>
    </article>`).join("");
  const empty = document.querySelector("#emptyWords");
  if (empty) empty.hidden = rows.length > 0;
}

function savedReadingCards() {
  return Object.values(savedWords)
    .filter((row) => row.word && row.translation)
    .map((row, index) => ({
      id: `Saved from Reading::${String(row.word).toLowerCase()}`,
      word: row.word,
      meaning: row.translation,
      category: "Saved from Reading",
      source: "reading",
      day: null,
      example: row.articleTitle || "",
      exampleTh: "",
      hasCuratedExample: Boolean(row.articleTitle),
      order: index + 1,
      frequencyRank: index + 1,
      audioWithSpelling: "",
      audioWithoutSpelling: "",
      audioProvider: "web-speech",
    }));
}

function mergeReadingCards(deck) {
  const readingCards = savedReadingCards();
  const cards = [...(deck.cards || []).filter((card) => card.category !== "Saved from Reading"), ...readingCards];
  const categories = [...(deck.categories || []).filter((category) => category.name !== "Saved from Reading")];
  if (readingCards.length) categories.push({ name: "Saved from Reading", count: readingCards.length });
  return { ...deck, cards, categories };
}

function renderSavedPage() {
  const container = document.querySelector("#savedArticleList");
  if (!container) return;
  const rows = Object.values(savedArticles).filter((row) => row.title && row.url);
  container.innerHTML = rows.map((row) => `
    <article class="story-card">
      <a class="story-image" href="${escapeHtml(row.url)}"><img src="${escapeHtml(row.image || "")}" alt=""></a>
      <div class="story-content">
        <div class="story-meta"><span>${escapeHtml(row.category || "")}</span><b class="level-chip ${(row.level || "").toLowerCase()}">${escapeHtml(row.level || "")}</b></div>
        <h3><a href="${escapeHtml(row.url)}">${escapeHtml(row.title)}</a></h3>
        <p>Saved ${escapeHtml((row.savedAt || "").slice(0, 10))}</p>
        <div class="card-actions"><a href="${escapeHtml(row.url)}">Read story</a><button data-remove-article="${escapeHtml(row.id)}" type="button">Remove</button></div>
      </div>
    </article>`).join("");
  const empty = document.querySelector("#emptySaved");
  if (empty) empty.hidden = rows.length > 0;
}

function formatTime(seconds) {
  if (!Number.isFinite(seconds)) return "0:00";
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}

function applyHomeFilters() {
  const panels = document.querySelectorAll("[data-home-day]");
  if (!panels.length) return;
  panels.forEach((panel) => {
    const activeDay = panel.dataset.homeDay === homeFilters.date;
    panel.classList.toggle("active", activeDay);
    if (!activeDay) return;

    let visibleCards = 0;
    panel.querySelectorAll(".story-card").forEach((card) => {
      const categoryMatch = homeFilters.category === "all" || card.dataset.category === homeFilters.category;
      const levelMatch = homeFilters.level === "all" || card.dataset.level === homeFilters.level;
      card.hidden = !(categoryMatch && levelMatch);
      if (!card.hidden) visibleCards += 1;
    });
    panel.querySelectorAll("[data-section-level]").forEach((section) => {
      const levelMatch = homeFilters.level === "all" || section.dataset.sectionLevel === homeFilters.level;
      const hasVisibleCard = Array.from(section.querySelectorAll(".story-card")).some((card) => !card.hidden);
      section.hidden = !(levelMatch && hasVisibleCard);
    });
    const featured = panel.querySelector(".featured-story");
    if (featured) {
      const categoryMatch = homeFilters.category === "all" || featured.dataset.category === homeFilters.category;
      const levelMatch = homeFilters.level === "all" || featured.dataset.level === homeFilters.level;
      featured.hidden = !(categoryMatch && levelMatch);
    }
    const empty = panel.querySelector(".home-filter-empty");
    if (empty) empty.hidden = visibleCards > 0;
  });
}

function initializeAudio() {
  const audio = document.querySelector("#storyAudio");
  if (!audio) return;
  const toggle = document.querySelector("#audioToggle");
  const progress = document.querySelector("#audioProgress");
  if (storySpeechSupported() && storyWords(audio).length) {
    storySpeech.words = storyWords(audio);
    storySpeech.duration = Math.max(8, storySpeech.words.length / (2.35 * storyRate()));
    updateStorySpeechProgress();
  }
  audio.playbackRate = Number(preferences.speed || 1);
  document.querySelectorAll("[data-speed]").forEach((button) => {
    button.classList.toggle("active", Number(button.dataset.speed) === audio.playbackRate);
  });
  audio.addEventListener("loadedmetadata", () => {
    document.querySelector("#audioDuration").textContent = formatTime(audio.duration);
  });
  audio.addEventListener("timeupdate", () => {
    document.querySelector("#audioCurrent").textContent = formatTime(audio.currentTime);
    progress.value = audio.duration ? String((audio.currentTime / audio.duration) * 100) : "0";
  });
  audio.addEventListener("ended", () => {
    toggle.querySelector("i").className = "fa-solid fa-play";
  });
  progress.addEventListener("input", () => {
    if (storySpeechSupported() && storySpeech.words.length) {
      const ratio = Number(progress.value) / 100;
      stopStorySpeech(false);
      storySpeech.index = Math.max(0, Math.min(storySpeech.words.length - 1, Math.floor(storySpeech.words.length * ratio)));
      storySpeech.elapsed = (storySpeech.duration || 0) * ratio;
      updateStorySpeechProgress();
      toggle.querySelector("i").className = "fa-solid fa-play";
    } else if (audio.duration) {
      audio.currentTime = Number(progress.value) / 100 * audio.duration;
    }
  });
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function addDaysIso(days) {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function defaultFlashcardState(card) {
  return {
    word: card.word,
    category: card.category,
    source: card.source || "podcast",
    state: "new",
    dueAt: todayIso(),
    intervalDays: 0,
    ease: 2.5,
    reps: 0,
    lapses: 0,
    lastReviewedAt: null,
  };
}

function getFlashcardState(card) {
  return flashcardProgress[card.id] || defaultFlashcardState(card);
}

function reviewFlashcard(card, rating) {
  const previous = getFlashcardState(card);
  let ease = Number(previous.ease || 2.5);
  let interval = Number(previous.intervalDays || 0);
  let state = previous.state || "new";
  let lapses = Number(previous.lapses || 0);

  if (rating === "again") {
    ease = Math.max(1.3, ease - 0.2);
    interval = 0;
    state = "learning";
    lapses += 1;
  } else if (rating === "hard") {
    ease = Math.max(1.3, ease - 0.15);
    interval = Math.max(1, Math.ceil(Math.max(1, interval) * 1.2));
    state = "learning";
  } else if (rating === "easy") {
    ease = Math.min(3.5, ease + 0.15);
    interval = interval > 0 ? Math.ceil(interval * (ease + 1.3)) : 7;
    state = interval >= 30 ? "mastered" : "review";
  } else {
    interval = interval > 0 ? Math.ceil(interval * ease) : 3;
    state = interval >= 21 ? "mastered" : "review";
  }

  flashcardProgress[card.id] = {
    ...previous,
    word: card.word,
    category: card.category,
    source: card.source || "podcast",
    state,
    dueAt: rating === "again" ? todayIso() : addDaysIso(interval),
    intervalDays: interval,
    ease,
    reps: Number(previous.reps || 0) + 1,
    lapses,
    lastReviewedAt: new Date().toISOString(),
  };
  writeObject(FLASHCARD_KEY, flashcardProgress);
}

function flashcardType() {
  return document.querySelector("#flashcardType")?.value || "en-th";
}

function flashcardMatchesStatus(card, status) {
  const progress = getFlashcardState(card);
  const due = progress.state === "new" || (progress.dueAt || todayIso()) <= todayIso();
  if (status === "all") return true;
  if (status === "due") return due;
  if (status === "new") return progress.state === "new";
  if (status === "learning") return progress.state === "learning" || progress.state === "review";
  if (status === "mastered") return progress.state === "mastered";
  return true;
}

function filteredFlashcards() {
  const category = document.querySelector("#flashcardCategory")?.value || "all";
  const day = document.querySelector("#flashcardDay")?.value || "all";
  const type = flashcardType();
  const status = document.querySelector("#flashcardStatus")?.value || "due";
  return (flashcardDeck.data?.cards || [])
    .filter((card) => category === "all" || card.category === category)
    .filter((card) => day === "all" || String(card.day || "") === day)
    .filter((card) => type !== "cloze" || card.hasCuratedExample)
    .filter((card) => flashcardMatchesStatus(card, status))
    .sort((a, b) => {
      const aState = getFlashcardState(a);
      const bState = getFlashcardState(b);
      if (aState.state === "new" && bState.state !== "new") return -1;
      if (aState.state !== "new" && bState.state === "new") return 1;
      return String(aState.dueAt || "").localeCompare(String(bState.dueAt || "")) ||
        (a.frequencyRank || a.order || 0) - (b.frequencyRank || b.order || 0);
    })
    .slice(0, 20);
}

function flashcardPrompt(card) {
  const type = flashcardType();
  if (type === "th-en") return card.meaning;
  if (type === "cloze") {
    const escaped = card.word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const pattern = new RegExp(escaped, "i");
    return pattern.test(card.example) ? card.example.replace(pattern, "_____") : `${card.example} (${card.meaning})`;
  }
  return card.word;
}

function flashcardAnswer(card) {
  const type = flashcardType();
  if (type === "th-en") return card.word;
  if (type === "cloze") return `${card.word} - ${card.meaning}`;
  return card.meaning;
}

function updateFlashcardDayOptions() {
  const select = document.querySelector("#flashcardDay");
  if (!select || !flashcardDeck.data) return;
  const category = document.querySelector("#flashcardCategory")?.value || "all";
  const days = [...new Set(flashcardDeck.data.cards
    .filter((card) => category === "all" || card.category === category)
    .map((card) => card.day)
    .filter(Boolean))]
    .sort((a, b) => a - b);
  const current = select.value;
  select.innerHTML = `<option value="all">All days</option>${days.map((day) => `<option value="${day}">Day ${day}</option>`).join("")}`;
  select.value = days.some((day) => String(day) === current) ? current : "all";
}

function renderFlashcardStats() {
  const stats = document.querySelector("#flashcardStats");
  if (!stats || !flashcardDeck.data) return;
  const category = document.querySelector("#flashcardCategory")?.value || "all";
  const cards = flashcardDeck.data.cards.filter((card) => category === "all" || card.category === category);
  const due = cards.filter((card) => flashcardMatchesStatus(card, "due")).length;
  const fresh = cards.filter((card) => getFlashcardState(card).state === "new").length;
  stats.innerHTML = `
    <span><b>${due}</b><small>Due</small></span>
    <span><b>${fresh}</b><small>New</small></span>
    <span><b>${cards.length}</b><small>Total</small></span>`;
}

function renderFlashcard() {
  const stage = document.querySelector("#flashcardStage");
  if (!stage) return;
  updateFlashcardDayOptions();
  renderFlashcardStats();
  flashcardDeck.cards = filteredFlashcards();
  flashcardDeck.index = Math.min(flashcardDeck.index, Math.max(0, flashcardDeck.cards.length - 1));
  const card = flashcardDeck.cards[flashcardDeck.index];
  if (!card) {
    stage.innerHTML = `
      <div class="flashcard-empty">
        <i class="fa-regular fa-circle-check"></i>
        <h2>No cards in this session</h2>
        <p>Try another category, card type, or status filter.</p>
      </div>`;
    return;
  }
  const progress = getFlashcardState(card);
  const answer = flashcardDeck.revealed ? `
    <div class="flashcard-answer">
      <span>Answer</span>
      <strong>${escapeHtml(flashcardAnswer(card))}</strong>
      ${card.example ? `<p>${escapeHtml(card.example)}${card.exampleTh ? ` - ${escapeHtml(card.exampleTh)}` : ""}</p>` : ""}
    </div>
    <div class="flashcard-rating">
      <button data-flashcard-rating="again" type="button">Again<span>today</span></button>
      <button data-flashcard-rating="hard" type="button">Hard<span>+1 day</span></button>
      <button data-flashcard-rating="good" type="button">Good<span>grow</span></button>
      <button data-flashcard-rating="easy" type="button">Easy<span>faster</span></button>
    </div>` : `<button class="primary-button flashcard-show" data-flashcard-action="show" type="button">Show answer</button>`;
  stage.innerHTML = `
    <article class="flashcard-card">
      <div class="flashcard-meta">
        <span>${escapeHtml(card.category)}</span>
        ${card.day ? `<span>Day ${card.day}</span>` : ""}
        <span>${escapeHtml(progress.state)}</span>
        <span>Due ${escapeHtml(progress.dueAt || todayIso())}</span>
      </div>
      <button class="flashcard-audio" data-flashcard-action="audio" type="button" aria-label="Play card audio"><i class="fa-solid fa-volume-high"></i></button>
      <div class="flashcard-prompt">
        <span>${flashcardType().toUpperCase()}</span>
        <h2>${escapeHtml(flashcardPrompt(card))}</h2>
      </div>
      ${answer}
      <footer class="flashcard-footer">
        <button data-flashcard-action="previous" type="button">Previous</button>
        <span>${flashcardDeck.index + 1} / ${flashcardDeck.cards.length}</span>
        <button data-flashcard-action="next" type="button">Next</button>
      </footer>
    </article>`;
}

function playFlashcardAudio(card) {
  if (!card) return;
  const source = card.audioWithoutSpelling || card.audioWithSpelling || "";
  if (!source) {
    speakWord(card.word);
    return;
  }
  if (flashcardAudio) flashcardAudio.pause();
  flashcardAudio = new Audio(`${document.body.dataset.basePrefix || ""}${source}`);
  flashcardAudio.play().catch(() => speakWord(card.word));
}

async function initializeFlashcards() {
  const stage = document.querySelector("#flashcardStage");
  if (!stage) return;
  try {
    const base = document.body.dataset.basePrefix || "";
    const response = await fetch(`${base}data/podcast-flashcards.json`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    flashcardDeck.data = mergeReadingCards(await response.json());
    const categorySelect = document.querySelector("#flashcardCategory");
    categorySelect.innerHTML = `<option value="all">All podcast categories</option>${(flashcardDeck.data.categories || []).map((category) =>
      `<option value="${escapeHtml(category.name)}">${escapeHtml(category.name)} (${category.count})</option>`).join("")}`;
    renderFlashcard();
  } catch (error) {
    stage.innerHTML = `
      <div class="flashcard-empty">
        <i class="fa-solid fa-triangle-exclamation"></i>
        <h2>Flashcards data not ready</h2>
        <p>Run the podcast flashcard data builder, then reload this page.</p>
      </div>`;
  }
}

document.addEventListener("click", (event) => {
  const flashcardAction = event.target.closest("[data-flashcard-action]");
  if (flashcardAction) {
    const card = flashcardDeck.cards[flashcardDeck.index];
    const action = flashcardAction.dataset.flashcardAction;
    if (action === "show") {
      flashcardDeck.revealed = true;
      renderFlashcard();
    } else if (action === "audio") {
      playFlashcardAudio(card);
    } else if (action === "previous") {
      flashcardDeck.index = Math.max(0, flashcardDeck.index - 1);
      flashcardDeck.revealed = false;
      renderFlashcard();
    } else if (action === "next") {
      flashcardDeck.index = Math.min(Math.max(0, flashcardDeck.cards.length - 1), flashcardDeck.index + 1);
      flashcardDeck.revealed = false;
      renderFlashcard();
    }
    return;
  }

  const flashcardRating = event.target.closest("[data-flashcard-rating]");
  if (flashcardRating) {
    const card = flashcardDeck.cards[flashcardDeck.index];
    if (card) reviewFlashcard(card, flashcardRating.dataset.flashcardRating);
    flashcardDeck.revealed = false;
    renderFlashcard();
    return;
  }

  const articleButton = event.target.closest("[data-save-article]");
  if (articleButton) {
    const article = articleFromButton(articleButton);
    if (savedArticles[article.id]) delete savedArticles[article.id];
    else savedArticles[article.id] = article;
    writeObject(ARTICLE_KEY, savedArticles);
    refreshArticleButtons();
    renderSavedPage();
    return;
  }

  const removeArticle = event.target.closest("[data-remove-article]");
  if (removeArticle) {
    delete savedArticles[removeArticle.dataset.removeArticle];
    writeObject(ARTICLE_KEY, savedArticles);
    renderSavedPage();
    refreshArticleButtons();
    return;
  }

  const wordTarget = event.target.closest(".word");
  if (wordTarget) {
    openWord(wordTarget);
    return;
  }

  if (event.target.closest("#speakPopoverWord")) {
    speakWord(activeWord?.word);
    return;
  }

  const speakButton = event.target.closest("[data-speak]");
  if (speakButton) {
    speakWord(speakButton.dataset.speak);
    return;
  }

  if (event.target.closest("#learnWord") && activeWord) {
    const key = activeWord.word.toLowerCase();
    if (savedWords[key]) delete savedWords[key];
    else savedWords[key] = activeWord;
    writeObject(WORD_KEY, savedWords);
    document.querySelector("#learnWord").classList.toggle("active", Boolean(savedWords[key]));
    renderArticleSavedWords();
    renderVocabularyPage(document.querySelector("#wordSearch")?.value || "");
    return;
  }

  const removeWord = event.target.closest("[data-remove-word]");
  if (removeWord) {
    delete savedWords[removeWord.dataset.removeWord];
    writeObject(WORD_KEY, savedWords);
    renderArticleSavedWords();
    renderVocabularyPage(document.querySelector("#wordSearch")?.value || "");
    return;
  }

  if (event.target.closest("#knownWord")) {
    event.target.closest("#knownWord").classList.toggle("active");
    return;
  }

  if (event.target.closest("#closeVocabPopover")) {
    document.querySelector("#vocabPopover").hidden = true;
    return;
  }

  const translate = event.target.closest(".translate-toggle");
  if (translate) {
    const panel = document.querySelector("#fullTranslation");
    panel.hidden = !panel.hidden;
    translate.classList.toggle("active", !panel.hidden);
    return;
  }

  const font = event.target.closest("[data-font-action]");
  if (font) {
    const delta = font.dataset.fontAction === "increase" ? 0.1 : -0.1;
    preferences.fontScale = Math.min(1.4, Math.max(0.8, Number(preferences.fontScale || 1) + delta));
    document.documentElement.style.setProperty("--reader-scale", preferences.fontScale);
    writeObject(PREF_KEY, preferences);
    return;
  }

  const audioToggle = event.target.closest("#audioToggle");
  if (audioToggle) {
    const audio = document.querySelector("#storyAudio");
    if (storySpeechSupported() && storyWords(audio).length) {
      if (storySpeech.playing) {
        pauseStorySpeech(audioToggle);
      } else {
        audio.pause();
        playStorySpeech(audio, audioToggle);
      }
    } else if (audio.paused) {
      audio.play().then(() => {
        audioToggle.querySelector("i").className = "fa-solid fa-pause";
      }).catch(() => {
        audioToggle.querySelector("i").className = "fa-solid fa-play";
      });
    } else {
      audio.pause();
      audioToggle.querySelector("i").className = "fa-solid fa-play";
    }
    return;
  }

  const speed = event.target.closest("[data-speed]");
  if (speed) {
    const audio = document.querySelector("#storyAudio");
    audio.playbackRate = Number(speed.dataset.speed);
    preferences.speed = audio.playbackRate;
    writeObject(PREF_KEY, preferences);
    document.querySelectorAll("[data-speed]").forEach((button) => button.classList.toggle("active", button === speed));
    if (storySpeechSupported() && storySpeech.words.length) {
      const wasPlaying = storySpeech.playing;
      pauseStorySpeech(document.querySelector("#audioToggle"));
      storySpeech.duration = Math.max(8, storySpeech.words.length / (2.35 * storyRate()));
      updateStorySpeechProgress();
      if (wasPlaying) playStorySpeech(audio, document.querySelector("#audioToggle"));
    }
    return;
  }

  const category = event.target.closest("#categoryFilters [data-category]");
  if (category) {
    document.querySelectorAll("#categoryFilters [data-category]").forEach((button) => button.classList.toggle("active", button === category));
    homeFilters.category = category.dataset.category;
    applyHomeFilters();
    return;
  }

  const dateButton = event.target.closest("#homeDateFilters [data-home-date]");
  if (dateButton) {
    document.querySelectorAll("#homeDateFilters [data-home-date]").forEach((button) => button.classList.toggle("active", button === dateButton));
    homeFilters.date = dateButton.dataset.homeDate;
    applyHomeFilters();
    document.querySelector("#homeDashboard")?.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }

  const levelButton = event.target.closest("#homeLevelFilters [data-home-level]");
  if (levelButton && !levelButton.disabled) {
    document.querySelectorAll("#homeLevelFilters [data-home-level]").forEach((button) => button.classList.toggle("active", button === levelButton));
    homeFilters.level = levelButton.dataset.homeLevel;
    applyHomeFilters();
    return;
  }

  if (!event.target.closest("#vocabPopover")) {
    const popover = document.querySelector("#vocabPopover");
    if (popover) popover.hidden = true;
  }
});

document.querySelector("#wordSearch")?.addEventListener("input", (event) => renderVocabularyPage(event.target.value));

function filterDaily() {
  const level = document.querySelector("#levelFilter")?.value || "all";
  const category = (document.querySelector("#dailyCategoryFilter")?.value || "all").toLowerCase();
  document.querySelectorAll("#dailyList .story-card").forEach((card) => {
    card.hidden = (level !== "all" && card.dataset.level !== level) ||
      (category !== "all" && card.dataset.category !== category);
  });
}

document.querySelector("#levelFilter")?.addEventListener("change", filterDaily);
document.querySelector("#dailyCategoryFilter")?.addEventListener("change", filterDaily);
document.querySelector("#flashcardCategory")?.addEventListener("change", () => {
  flashcardDeck.index = 0;
  flashcardDeck.revealed = false;
  renderFlashcard();
});
document.querySelector("#flashcardDay")?.addEventListener("change", () => {
  flashcardDeck.index = 0;
  flashcardDeck.revealed = false;
  renderFlashcard();
});
document.querySelector("#flashcardType")?.addEventListener("change", () => {
  flashcardDeck.index = 0;
  flashcardDeck.revealed = false;
  renderFlashcard();
});
document.querySelector("#flashcardStatus")?.addEventListener("change", () => {
  flashcardDeck.index = 0;
  flashcardDeck.revealed = false;
  renderFlashcard();
});
document.querySelector("#mobileHomeDate")?.addEventListener("change", (event) => {
  homeFilters.date = event.target.value;
  document.querySelectorAll("#homeDateFilters [data-home-date]").forEach((button) => {
    button.classList.toggle("active", button.dataset.homeDate === homeFilters.date);
  });
  applyHomeFilters();
});
document.querySelector("#mobileHomeLevel")?.addEventListener("change", (event) => {
  homeFilters.level = event.target.value;
  document.querySelectorAll("#homeLevelFilters [data-home-level]").forEach((button) => {
    button.classList.toggle("active", button.dataset.homeLevel === homeFilters.level);
  });
  applyHomeFilters();
});
document.querySelector("#mobileHomeCategory")?.addEventListener("change", (event) => {
  homeFilters.category = event.target.value;
  document.querySelectorAll("#categoryFilters [data-category]").forEach((button) => {
    button.classList.toggle("active", button.dataset.category === homeFilters.category);
  });
  applyHomeFilters();
});
window.addEventListener("resize", () => {
  const popover = document.querySelector("#vocabPopover");
  if (popover) popover.hidden = true;
});
document.querySelectorAll(".word").forEach((word) => {
  word.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openWord(word);
    }
  });
});

document.documentElement.style.setProperty("--reader-scale", Number(preferences.fontScale || 1));
const initialDateButton = document.querySelector("#homeDateFilters [data-home-date]");
if (initialDateButton) homeFilters.date = initialDateButton.dataset.homeDate;
applyHomeFilters();
refreshArticleButtons();
renderArticleSavedWords();
renderVocabularyPage();
renderSavedPage();
initializeAudio();
initializeFlashcards();
