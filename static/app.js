/*
 * Setu client.
 *
 * Speech in and speech out use the browser's own APIs by default — they cost
 * nothing, need no key, and work offline for TTS. The server is only asked for
 * ASR when the browser cannot do it, which per the blueprint is the common case
 * on iOS Safari.
 */

(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const ui = {
    status: $("status"),
    sourceLang: $("sourceLang"),
    targetLang: $("targetLang"),
    swapLangs: $("swapLangs"),
    registerChips: $("registerChips"),
    addresseeChips: $("addresseeChips"),
    soften: $("soften"),
    keepEnglish: $("keepEnglish"),
    levelHint: $("levelHint"),
    asrHint: $("asrHint"),
    sourceText: $("sourceText"),
    micBtn: $("micBtn"),
    micLabel: $("micLabel"),
    translateBtn: $("translateBtn"),
    speakBtn: $("speakBtn"),
    warning: $("warning"),
    resultPanel: $("resultPanel"),
    outputText: $("outputText"),
    detectedRegister: $("detectedRegister"),
    badgeRegister: $("badgeRegister"),
    badgeEngine: $("badgeEngine"),
    badgeTiming: $("badgeTiming"),
    traceWrap: $("traceWrap"),
    traceCount: $("traceCount"),
    trace: $("trace"),
    ladderPanel: $("ladderPanel"),
    ladder: $("ladder"),
    phrasebookStats: $("phrasebookStats"),
    pad: $("pad"),
    padWrap: $("padWrap"),
    padNote: $("padNote"),
    learnLang: $("learnLang"),
    learnRel: $("learnRel"),
    learnText: $("learnText"),
    learnCheck: $("learnCheck"),
    learnFeedback: $("learnFeedback"),
    learnVerdict: $("learnVerdict"),
    learnMessage: $("learnMessage"),
    learnSuggestionWrap: $("learnSuggestionWrap"),
    learnSuggestion: $("learnSuggestion"),
    learnEvidence: $("learnEvidence"),
    peopleList: $("peopleList"),
    peopleHint: $("peopleHint"),
    personName: $("personName"),
    personSave: $("personSave"),
    personNote: $("personNote"),
    convoSetup: $("convoSetup"),
    convoLive: $("convoLive"),
    convoHint: $("convoHint"),
    convoAName: $("convoAName"),
    convoBName: $("convoBName"),
    convoALang: $("convoALang"),
    convoBLang: $("convoBLang"),
    convoAReg: $("convoAReg"),
    convoBReg: $("convoBReg"),
    convoStart: $("convoStart"),
    convoMeta: $("convoMeta"),
    transcript: $("transcript"),
    convoSpeaker: $("convoSpeaker"),
    convoText: $("convoText"),
    convoSay: $("convoSay"),
    convoEnd: $("convoEnd"),
  };

  const state = {
    register: "auto",
    addressee: "",
    languages: [],
    byCode: new Map(),
    lastResult: null,
    listening: false,
    busy: false,
    // Speculative translation of what is being said right now. `seq` rises
    // with every partial sent; a result whose seq is not the current one has
    // been overtaken and is dropped.
    partial: { seq: 0, text: "", sentAt: 0, showing: false },
    convo: {
      id: null,
      a: { register: "auto" },
      b: { register: "auto" },
      speaker: "",
      shown: 0,   // shifts already announced, so they are not repeated
    },
    learner: { relationship: "stranger" },
    people: [],
  };

  const ADDRESSEES = [
    ["", "Not set"],
    ["older_man", "Older man"],
    ["older_woman", "Older woman"],
    ["elder_man", "Elder (m)"],
    ["elder_woman", "Elder (f)"],
    ["peer", "Peer"],
    ["official", "Official"],
  ];

  // ---------------------------------------------------------------- status

  function setStatus(text, stateName) {
    ui.status.textContent = text;
    ui.status.dataset.state = stateName || "ready";
  }

  // ------------------------------------------------------------ bootstrap

  async function boot() {
    buildRegisterChips();
    buildAddresseeChips();
    buildConversation();
    ui.pad.addEventListener("click", padClick);
    buildLearner();
    wireEvents();

    try {
      const res = await fetch("/api/languages");
      const data = await res.json();
      state.languages = data.languages;
      data.languages.forEach((l) => state.byCode.set(l.code, l));
      fillLanguageSelects(data.languages);
      setStatus("Ready", "ready");
    } catch (err) {
      setStatus("Offline", "error");
    }

    refreshPhrasebook();
    setupSocket();
    setupSpeechRecognition();
    updateLevelHint();
    registerServiceWorker();
  }

  function fillLanguageSelects(languages) {
    const opts = languages
      .map((l) => `<option value="${l.code}">${l.name}</option>`)
      .join("");
    ui.sourceLang.insertAdjacentHTML("beforeend", opts);
    ui.targetLang.innerHTML = opts;
    ui.sourceLang.value = "en";
    ui.targetLang.value = "bn";

    // Conversation mode needs both sides named explicitly — there is no
    // "detect automatically" for a participant, because their language is a
    // property of the person rather than of the sentence.
    ui.convoALang.innerHTML = opts;
    ui.convoBLang.innerHTML = opts;
    ui.convoALang.value = "bn";
    ui.convoBLang.value = "en";

    // Learner mode practises a language rather than translating into one, so
    // it gets its own select, defaulting to the one you are learning to speak.
    ui.learnLang.innerHTML = opts;
    ui.learnLang.value = "bn";

    updateLevelHint();
    loadPad();
    // After the languages, so each saved contact can show its language by name.
    buildPeople();
  }

  function buildRegisterChips() {
    const levels = [
      ["auto", "Auto", "Mirror the speaker"],
      ["close", "Close", "তুই · तू · du"],
      ["casual", "Casual", "তুমি · तुम · du"],
      ["polite", "Polite", "আপনি · आप · Sie"],
      ["formal", "Formal", "Most deferential"],
    ];
    ui.registerChips.innerHTML = levels
      .map(
        ([slug, label, title]) =>
          `<button class="chip" role="radio" data-level="${slug}" title="${title}"
             aria-checked="${slug === "auto"}">${label}</button>`
      )
      .join("");

    ui.registerChips.addEventListener("click", (e) => {
      const chip = e.target.closest(".chip");
      if (!chip) return;
      state.register = chip.dataset.level;
      syncChecked(ui.registerChips, "level", state.register);
      updateLevelHint();
      // Re-levelling is free and needs no network, so do it immediately.
      if (state.lastResult) relevel();
    });
  }

  function buildAddresseeChips() {
    ui.addresseeChips.innerHTML = ADDRESSEES.map(
      ([value, label]) =>
        `<button class="chip" role="radio" data-addressee="${value}"
           aria-checked="${value === ""}">${label}</button>`
    ).join("");

    ui.addresseeChips.addEventListener("click", (e) => {
      const chip = e.target.closest(".chip");
      if (!chip) return;
      state.addressee = chip.dataset.addressee;
      syncChecked(ui.addresseeChips, "addressee", state.addressee);
    });
  }

  function syncChecked(container, key, value) {
    container.querySelectorAll(".chip").forEach((c) => {
      c.setAttribute("aria-checked", String(c.dataset[key] === value));
    });
  }

  /*
   * Mark the register chips a language does not actually distinguish. German
   * has one form for Close and Casual; saying so up front is more honest than
   * letting someone tap "Close" and wonder why nothing changed.
   */
  function updateLevelHint() {
    const lang = state.byCode.get(ui.targetLang.value);
    if (!lang) {
      ui.levelHint.textContent = "";
      return;
    }
    const distinct = new Set(lang.distinct_levels);
    const slugs = ["close", "casual", "polite", "formal"];
    ui.registerChips.querySelectorAll(".chip").forEach((chip) => {
      const idx = slugs.indexOf(chip.dataset.level);
      chip.dataset.folded = idx >= 0 && !distinct.has(idx) ? "true" : "false";
    });
    const n = distinct.size;
    ui.levelHint.textContent =
      `${lang.name} distinguishes ${n} level${n === 1 ? "" : "s"} · ${lang.rule_count} rules`;
  }

  // ---------------------------------------------------------------- events

  function wireEvents() {
    ui.translateBtn.addEventListener("click", translate);
    ui.targetLang.addEventListener("change", () => {
      updateLevelHint();
      // Different languages divide the plane differently — that is the point
      // of drawing it per language rather than once — so it has to be redrawn.
      loadPad();
      if (state.lastResult) relevel();
    });
    ui.swapLangs.addEventListener("click", swapLanguages);
    // Re-run rather than re-level, so the ladder changes too. The phrasebook
    // already has the MT output, so this costs no network round trip.
    ui.keepEnglish.addEventListener("change", () => {
      if (state.lastResult) translate();
    });
    ui.speakBtn.addEventListener("click", () => {
      if (state.lastResult) speak(state.lastResult.translated_text, state.lastResult);
    });
    ui.micBtn.addEventListener("click", toggleMic);
    ui.sourceText.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") translate();
    });
    ui.ladder.addEventListener("click", (e) => {
      const li = e.target.closest("li");
      if (!li) return;
      speak(li.querySelector(".txt").textContent, state.lastResult);
    });
  }

  function swapLanguages() {
    const src = ui.sourceLang.value;
    const tgt = ui.targetLang.value;
    if (!src) return;              // "detect automatically" has nothing to swap
    ui.sourceLang.value = tgt;
    ui.targetLang.value = src;
    if (state.lastResult && state.lastResult.translated_text) {
      ui.sourceText.value = state.lastResult.translated_text;
    }
    updateLevelHint();
  }

  // ------------------------------------------------------------- translate

  async function translate() {
    const text = ui.sourceText.value.trim();
    if (!text || state.busy) return;

    state.busy = true;
    ui.translateBtn.disabled = true;
    // The real thing is on its way, so stop taking guesses and ignore any
    // still in flight.
    clearPartial();
    setStatus("Translating…", "busy");

    try {
      const res = await fetch("/api/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          source_lang: ui.sourceLang.value || null,
          target_lang: ui.targetLang.value,
          register: state.register,
          addressee: state.addressee || null,
          soften: ui.soften.checked,
          keep_english: ui.keepEnglish.checked,
          ladder: true,
        }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      render(data);
      setStatus(data.ok ? "Ready" : "Partial", data.ok ? "ready" : "error");
      refreshPhrasebook();
    } catch (err) {
      setStatus("Failed", "error");
      showWarning(String(err.message || err));
    } finally {
      state.busy = false;
      ui.translateBtn.disabled = false;
    }
  }

  /*
   * Re-render the existing translation at a new level. This is the offline
   * re-levelling the architecture makes possible: no MT call, no round trip
   * to any engine — just the rule tables.
   */
  async function relevel() {
    const prev = state.lastResult;
    if (!prev || !prev.translated_text) return;
    try {
      const res = await fetch("/api/relevel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: prev.mt_base || prev.translated_text,
          language: prev.target_language,
          register: state.register === "auto" ? "auto" : state.register,
          keep_english: ui.keepEnglish.checked,
          keep: (prev.code_switch && prev.code_switch.english_words) || [],
        }),
      });
      const data = await res.json();
      if (data.error) return;
      prev.translated_text = data.text;
      prev.register_name = data.level_name;
      prev.register_level = data.level;
      prev.formality_percentage = data.formality_percent;
      prev.edits = data.edits || [];
      // No MT call happened, so say so rather than keeping the old engine label.
      prev.engine = "register layer (offline)";
      prev.cached = false;
      prev.timings_ms = {};
      render(prev, { keepLadder: true });
    } catch (_) {
      /* offline: keep showing what we have */
    }
  }

  // ---------------------------------------------------------------- render

  function render(data, opts = {}) {
    // Keep the untouched MT output so re-levelling always starts from the
    // same base rather than compounding edits. Not the Casual rung: that has
    // Casual's English words in it, and they would leak into Formal.
    if (!opts.keepLadder) {
      data.mt_base = data.mt_text
        || (data.ladder && data.ladder.Casual)
        || data.translated_text;
    } else if (state.lastResult) {
      data.mt_base = state.lastResult.mt_base;
      data.ladder = state.lastResult.ladder;
    }
    state.lastResult = data;

    ui.resultPanel.hidden = false;
    delete ui.outputText.dataset.partial;   // this one is settled
    ui.outputText.setAttribute("aria-busy", "false");
    ui.outputText.textContent = data.translated_text || "";
    ui.outputText.lang = data.target_language || "";
    ui.speakBtn.disabled = !data.translated_text;

    ui.badgeRegister.textContent =
      `${data.register_name} · ${data.formality_percentage}%`;
    ui.badgeEngine.textContent = data.cached ? "phrasebook (0 ms)" : (data.engine || "");
    const t = data.timings_ms || {};
    ui.badgeTiming.textContent = t.total ? `${Math.round(t.total)} ms` : "";
    ui.badgeTiming.title = Object.entries(t)
      .map(([k, v]) => `${k}: ${v} ms`)
      .join("\n");

    const heard = [];
    if (data.detected_register_name) {
      heard.push(`You spoke in ${data.detected_register_name}`);
      const slang = (data.detected_slang || []).map((s) => s.term);
      if (slang.length) heard.push(`slang: ${slang.join(", ")}`);
    }
    // Reported as a count, never as a register: English can mark formality
    // or casualness depending on who is speaking and where.
    const mix = data.code_switch;
    if (mix && mix.english) {
      heard.push(
        `English: ${mix.english_words.join(", ")} ` +
        `(${mix.english} of ${mix.words} words)`
      );
    }
    ui.detectedRegister.textContent = heard.join(" · ");

    renderTrace(data.edits || []);
    if (!opts.keepLadder) renderLadder(data.ladder || {}, data.target_language);
    markCurrentRung(data.register_name);

    if (data.warning) showWarning(data.warning);
    else if (!data.ok && data.message) showWarning(data.message);
    else hideWarning();
  }

  function renderTrace(edits) {
    if (!edits.length) {
      ui.traceWrap.hidden = true;
      return;
    }
    ui.traceWrap.hidden = false;
    ui.traceCount.textContent = `(${edits.length})`;
    ui.trace.innerHTML = edits
      .map(
        (e) =>
          `<li><span class="before">${esc(e.before)}</span>` +
          `<span aria-hidden="true">→</span>` +
          `<span class="after">${esc(e.after)}</span>` +
          `<span class="rule">${esc(e.rule)}</span></li>`
      )
      .join("");
  }

  function renderLadder(ladder, language) {
    const order = ["Close", "Casual", "Polite", "Formal"];
    const rungs = order.filter((k) => ladder[k] !== undefined);
    if (!rungs.length) {
      ui.ladderPanel.hidden = true;
      return;
    }
    ui.ladderPanel.hidden = false;

    const seen = new Map();
    ui.ladder.innerHTML = rungs
      .map((name) => {
        const text = ladder[name];
        const dupOf = seen.get(text);
        if (dupOf === undefined) seen.set(text, name);
        return (
          `<li data-level="${name}">` +
          `<span class="lvl">${name}</span>` +
          // Tagged with the language it is in, so a screen reader reads
          // Bengali as Bengali instead of sounding out the page's English.
          `<span class="txt" dir="auto" lang="${esc(language || "")}">` +
          `${esc(text)}</span>` +
          (dupOf ? `<span class="same">same as ${dupOf}</span>` : "") +
          `</li>`
        );
      })
      .join("");
  }

  function markCurrentRung(name) {
    ui.ladder.querySelectorAll("li").forEach((li) => {
      li.dataset.current = String(li.dataset.level === name);
    });
  }

  function showWarning(msg) {
    ui.warning.textContent = msg;
    ui.warning.hidden = false;
  }
  function hideWarning() {
    ui.warning.hidden = true;
  }

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  // ------------------------------------------------------------- the pad

  /*
   * Register on two axes rather than one (blueprint 13.2 #1).
   *
   * Brown & Gilman, 1960: politeness is power and solidarity, and they are
   * independent. Your boss is high power and low solidarity; your grandmother
   * is high power and high solidarity. A single scale puts those two in the
   * same place and reaches for the distant pronoun with your grandmother.
   *
   * The whole plane is drawn, not only the named relationships, because the
   * argument *is* the shape: a row where respect is constant and the register
   * changes anyway. Twelve cells show that. Seven labels ask you to take it
   * on trust.
   */

  async function loadPad() {
    const lang = ui.targetLang.value;
    if (!lang) return;
    try {
      const res = await fetch(`/api/register/pad?lang=${encodeURIComponent(lang)}`);
      const data = await res.json();
      renderPad(data);
    } catch (err) {
      ui.pad.innerHTML = "";
    }
  }

  function renderPad(data) {
    const grid = data.grid || [];
    if (!grid.length) {
      ui.padWrap.hidden = true;
      return;
    }
    ui.padWrap.hidden = false;

    // Respect descending, so "more respect" is up — which is the only way the
    // vertical axis label means anything.
    const powers = [...new Set(grid.map((c) => c.power))].sort((a, b) => b - a);
    const closeness = [...new Set(grid.map((c) => c.solidarity))].sort();

    // A grid is rows of cells, and screen readers rely on that nesting to
    // report "row 2, column 3" — which is the whole argument the pad makes:
    // respect held constant along a row while the register changes anyway.
    ui.pad.innerHTML = powers
      .map((p) => {
        const cells = closeness
          .map((s) => {
            const cell = grid.find((c) => c.power === p && c.solidarity === s);
            if (!cell) return "";
            const where = `${cell.power_label} · ${cell.solidarity_label}`;
            const label = cell.named
              ? `${cell.level_name} — ${cell.label}, ${where}`
              : `${cell.level_name} — ${where}`;
            return (
              `<button role="gridcell" data-level="${esc(cell.level_name)}"` +
              ` data-named="${Boolean(cell.named)}" data-power="${p}"` +
              ` data-solidarity="${s}" aria-selected="false"` +
              ` aria-label="${esc(label)}" title="${esc(where)}">` +
              `<span class="lv">${esc(cell.level_name)}</span>` +
              `<span class="nm">${cell.named ? esc(cell.label) : ""}</span>` +
              `</button>`
            );
          })
          .join("");
        return cells ? `<div role="row">${cells}</div>` : "";
      })
      .join("");

    ui.padNote.textContent = "";
  }

  function padClick(e) {
    const cell = e.target.closest("button");
    if (!cell) return;
    ui.pad.querySelectorAll("button").forEach((b) =>
      b.setAttribute("aria-selected", String(b === cell))
    );

    // The pad is a way of choosing a register, so it drives the same control
    // the chips do rather than a parallel one.
    state.register = cell.dataset.level.toLowerCase();
    syncChecked(ui.registerChips, "level", state.register);
    updateLevelHint();

    const name = cell.querySelector(".nm").textContent;
    ui.padNote.textContent = name
      ? `${name} — ${cell.dataset.level.toLowerCase()} here.`
      : `${cell.title} — ${cell.dataset.level.toLowerCase()} here.`;

    if (state.lastResult) relevel();
  }

  // ---------------------------------------------------------- learner mode

  /*
   * The pipeline run backwards. You say something the way you would say it to
   * a particular person, and instead of translating, this tells you how it
   * lands. No language app teaches register, which is the thing that actually
   * decides whether you sound rude.
   */

  const VERDICT_TITLES = {
    good: "That fits.",
    too_familiar: "Too familiar for them.",
    too_formal: "A little distant.",
    unknown: "Nothing to judge yet.",
  };

  async function buildLearner() {
    ui.learnCheck.addEventListener("click", checkLearner);
    ui.learnText.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) checkLearner();
    });
    ui.learnRel.addEventListener("click", (e) => {
      const chip = e.target.closest(".chip");
      if (!chip) return;
      state.learner.relationship = chip.dataset.rel;
      syncChecked(ui.learnRel, "rel", chip.dataset.rel);
    });

    try {
      const res = await fetch("/api/learner/relationships");
      const data = await res.json();
      const rels = data.relationships || [];
      state.learner.relationship = rels.length ? rels[0].key : "stranger";
      ui.learnRel.innerHTML = rels
        .map(
          (r, i) =>
            `<button class="chip" role="radio" data-rel="${esc(r.key)}"
               aria-checked="${i === 0}" title="${esc(r.why)}">${esc(r.label)}</button>`
        )
        .join("");
    } catch (err) {
      ui.learnRel.innerHTML = "";
    }
  }

  async function checkLearner() {
    const text = ui.learnText.value.trim();
    if (!text) return;
    ui.learnCheck.disabled = true;
    try {
      const res = await fetch("/api/learner/assess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          language: ui.learnLang.value,
          relationship: state.learner.relationship,
        }),
      });
      const fb = await res.json();
      if (!res.ok) throw new Error(fb.error || "could not check that");
      renderFeedback(fb);
    } catch (err) {
      showWarning(err.message);
    } finally {
      ui.learnCheck.disabled = false;
    }
  }

  function renderFeedback(fb) {
    ui.learnFeedback.hidden = false;
    ui.learnFeedback.dataset.verdict = fb.verdict;
    ui.learnVerdict.textContent = VERDICT_TITLES[fb.verdict] || fb.verdict;
    ui.learnMessage.textContent = fb.message || "";

    // Only offer a correction when there is one to make.
    ui.learnSuggestionWrap.hidden = !fb.suggestion;
    ui.learnSuggestion.textContent = fb.suggestion || "";
    ui.learnSuggestion.lang = ui.learnLang.value || "";

    // Show *which* words carried the register. A verdict with no reason is a
    // ruling; a verdict that points at তুই is a lesson.
    const ev = fb.evidence || [];
    ui.learnEvidence.textContent = ev.length
      ? `Read from: ${ev.join(", ")}`
      : "";
  }

  // ---------------------------------------------------- relationship memory

  /*
   * Register attached to a person. Everything here is local — a SQLite file on
   * this device, no sync, no export — because who you are deferential to is as
   * sensitive as a contact list gets. The UI says so where the data is entered
   * rather than in a policy nobody reads.
   */

  function buildPeople() {
    ui.personSave.addEventListener("click", rememberPerson);
    ui.personName.addEventListener("keydown", (e) => {
      if (e.key === "Enter") rememberPerson();
    });
    ui.peopleList.addEventListener("click", (e) => {
      const btn = e.target.closest("button");
      if (!btn) return;
      const name = btn.closest("li").dataset.name;
      if (btn.dataset.act === "use") usePerson(name);
      if (btn.dataset.act === "forget") forgetPerson(name);
    });
    refreshPeople();
  }

  async function refreshPeople() {
    try {
      const res = await fetch("/api/relationships");
      const data = await res.json();
      state.people = data.relationships || [];
      renderPeople();
    } catch (err) {
      ui.peopleList.innerHTML = "";
    }
  }

  function renderPeople() {
    ui.peopleList.innerHTML = state.people
      .map((p) => {
        const lang = state.byCode.get(p.language);
        const parts = [
          p.register_name || "no register saved",
          lang ? lang.name : p.language,
          p.addressee ? p.addressee.replace(/_/g, " ") : "",
        ].filter(Boolean);
        return (
          `<li data-name="${esc(p.name)}">` +
          `<span class="who">${esc(p.name)}</span>` +
          `<span class="how">${esc(parts.join(" · "))}</span>` +
          `<span class="acts">` +
          `<button class="ghost" data-act="use">Use</button>` +
          `<button class="ghost" data-act="forget" aria-label="Forget ${esc(p.name)}">Forget</button>` +
          `</span></li>`
        );
      })
      .join("");
    const n = state.people.length;
    ui.peopleHint.textContent = n
      ? `${n} ${n === 1 ? "person" : "people"} · this device only`
      : "Stored on this device only";
  }

  async function rememberPerson() {
    const name = ui.personName.value.trim();
    if (!name) {
      ui.personName.focus();
      return;
    }
    const body = {
      name,
      language: ui.targetLang.value,
      register: state.register,
      addressee: state.addressee || null,
    };
    ui.personSave.disabled = true;
    try {
      const res = await fetch("/api/relationships", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const saved = await res.json();
      if (!res.ok) throw new Error(saved.error || "could not remember that");
      ui.personName.value = "";
      // Auto is a way of not deciding, so there is nothing to remember. Say so
      // rather than silently saving a contact with no register.
      ui.personNote.textContent = state.register === "auto"
        ? `Saved ${saved.name}, but with no register — Auto mirrors whoever is speaking, so pick a level first if you want one remembered.`
        : `Saved ${saved.name} at ${saved.register_name}.`;
      await refreshPeople();
    } catch (err) {
      showWarning(err.message);
    } finally {
      ui.personSave.disabled = false;
    }
  }

  function usePerson(name) {
    const p = state.people.find((x) => x.name === name);
    if (!p) return;
    // Apply everything we know in one tap — which is the whole feature: the
    // second conversation with someone needs no configuration.
    if (p.language && state.byCode.has(p.language)) {
      ui.targetLang.value = p.language;
      updateLevelHint();
      loadPad();
    }
    if (p.register_slug) {
      state.register = p.register_slug;
      syncChecked(ui.registerChips, "level", state.register);
    }
    if (p.addressee) {
      state.addressee = p.addressee;
      syncChecked(ui.addresseeChips, "addressee", state.addressee);
    }
    ui.personNote.textContent = `Now speaking to ${p.name}.`;
    if (state.lastResult) relevel();
  }

  async function forgetPerson(name) {
    try {
      await fetch(`/api/relationships/${encodeURIComponent(name)}`, { method: "DELETE" });
      ui.personNote.textContent = `Forgot ${name}.`;
      await refreshPeople();
    } catch (err) {
      showWarning("could not remove that");
    }
  }

  // ---------------------------------------------------------- conversation

  /*
   * Two registers, one per direction — the thing no other translator does.
   *
   * Each side carries the register *it speaks in*, so a turn translates into
   * the listener's language at the speaker's level and the two never have to
   * agree. Auto on both sides is the interesting default: the elder speaks
   * down, you speak up, and nobody touches a control.
   */

  const CONVO_LEVELS = [
    ["auto", "Auto"], ["close", "Close"], ["casual", "Casual"],
    ["polite", "Polite"], ["formal", "Formal"],
  ];

  function buildConversation() {
    [["a", ui.convoAReg], ["b", ui.convoBReg]].forEach(([side, box]) => {
      box.innerHTML = CONVO_LEVELS.map(
        ([slug, label]) =>
          `<button class="chip" role="radio" data-level="${slug}"
             aria-checked="${slug === "auto"}">${label}</button>`
      ).join("");
      box.addEventListener("click", (e) => {
        const chip = e.target.closest(".chip");
        if (!chip) return;
        state.convo[side].register = chip.dataset.level;
        syncChecked(box, "level", chip.dataset.level);
      });
    });

    ui.convoStart.addEventListener("click", startConversation);
    ui.convoSay.addEventListener("click", sendTurn);
    ui.convoEnd.addEventListener("click", endConversation);
    ui.convoText.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) sendTurn();
    });
    ui.convoSpeaker.addEventListener("click", (e) => {
      const chip = e.target.closest(".chip");
      if (!chip) return;
      state.convo.speaker = chip.dataset.speaker;
      syncChecked(ui.convoSpeaker, "speaker", state.convo.speaker);
      ui.convoText.focus();
    });
  }

  async function startConversation() {
    const a = { name: ui.convoAName.value.trim() || "Them",
                language: ui.convoALang.value,
                register: state.convo.a.register };
    const b = { name: ui.convoBName.value.trim() || "You",
                language: ui.convoBLang.value,
                register: state.convo.b.register };
    if (a.name === b.name) b.name = `${b.name} (2)`;

    ui.convoStart.disabled = true;
    try {
      const res = await fetch("/api/conversation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ a, b }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "could not start");

      state.convo.id = data.id;
      state.convo.names = [a.name, b.name];
      state.convo.speaker = a.name;
      state.convo.shown = 0;
      ui.transcript.innerHTML = "";

      ui.convoSpeaker.innerHTML = [a, b]
        .map(
          (p, i) =>
            `<button class="chip" role="radio" data-speaker="${esc(p.name)}"
               aria-checked="${i === 0}">${esc(p.name)} speaking</button>`
        )
        .join("");

      ui.convoSetup.hidden = true;
      ui.convoLive.hidden = false;
      renderConversation(data);
      ui.convoText.focus();
    } catch (err) {
      showWarning(err.message);
    } finally {
      ui.convoStart.disabled = false;
    }
  }

  async function sendTurn() {
    const text = ui.convoText.value.trim();
    if (!text || !state.convo.id) return;
    ui.convoSay.disabled = true;
    try {
      const res = await fetch(`/api/conversation/${state.convo.id}/say`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ speaker: state.convo.speaker, text }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "turn failed");

      ui.convoText.value = "";
      renderConversation(data.conversation);
      // Hand the turn over, which is what happens in a real conversation and
      // saves a tap in the common case.
      const names = state.convo.names || [];
      const other = names.find((n) => n !== state.convo.speaker);
      if (other) {
        state.convo.speaker = other;
        syncChecked(ui.convoSpeaker, "speaker", other);
      }
    } catch (err) {
      showWarning(err.message);
    } finally {
      ui.convoSay.disabled = false;
      ui.convoText.focus();
    }
  }

  function endConversation() {
    state.convo.id = null;
    ui.convoLive.hidden = true;
    ui.convoSetup.hidden = false;
    ui.convoHint.textContent = "Two people, two registers";
  }

  function renderConversation(convo) {
    const observed = convo.observed_registers || {};
    const participants = convo.participants || {};
    const names = Object.keys(participants);
    const side = new Map(names.map((n, i) => [n, i === 0 ? "a" : "b"]));

    ui.convoMeta.innerHTML =
      names
        .map((n) => {
          const level = observed[n];
          return `<span><span class="who">${esc(n)}</span> ` +
                 `${level ? esc(level) : "—"}</span>`;
        })
        .join('<span aria-hidden="true">·</span>') +
      (convo.asymmetric
        ? '<span class="asym">asymmetric — each side has its own register</span>'
        : "");

    // Turns and shifts share one stream, because a shift belongs where it
    // happened rather than in a summary nobody reads.
    const shiftAt = new Map();
    (convo.shifts || []).forEach((s) => {
      if (!shiftAt.has(s.at_turn)) shiftAt.set(s.at_turn, []);
      shiftAt.get(s.at_turn).push(s);
    });

    ui.transcript.innerHTML = (convo.turns || [])
      .map((turn, i) => {
        // Both sides can be set to the same language, and then the two lines
        // are identical — printing the sentence twice looks like a bug rather
        // than a translation.
        const echoed = turn.translated && turn.translated !== turn.text;
        // Each line is tagged with the language it is actually in — the
        // speaker's for what they said, the listener's for what they heard —
        // so a screen reader switches voice with the conversation.
        const spoke = participants[turn.speaker] || {};
        const listener = Object.values(participants).find(
          (p) => p.name !== turn.speaker
        ) || {};
        const rows = [
          `<li data-side="${side.get(turn.speaker) || "a"}">` +
            `<p class="said" lang="${esc(spoke.language || "")}" dir="auto">` +
            `${esc(turn.speaker)}: ${esc(turn.text)}</p>` +
            (echoed
              ? `<p class="heard" dir="auto" lang="${esc(listener.language || "")}">` +
                `${esc(turn.translated)}</p>`
              : "") +
            `<div class="tmeta"><span>sent as ${esc(turn.register_name)}</span>` +
            (turn.detected_name
              ? `<span>read as ${esc(turn.detected_name)}</span>`
              : "<span>no register marker</span>") +
            `</div></li>`,
        ];
        (shiftAt.get(i) || []).forEach((s) => {
          rows.push(`<li class="shift">${esc(s.message)}</li>`);
        });
        return rows.join("");
      })
      .join("");
    ui.transcript.scrollTop = ui.transcript.scrollHeight;

    const shifts = convo.shifts || [];
    ui.convoHint.textContent = shifts.length
      ? shifts[shifts.length - 1].message
      : `${(convo.turns || []).length} turns`;
  }

  // ------------------------------------------------------------------- TTS

  /*
   * Register drives the voice, not just the words: formal output is delivered
   * slower and slightly lower. The browser's own voices are already installed
   * on every phone and cost nothing, so they are the default.
   */
  function speak(text, result) {
    if (!text || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();

    const utter = new SpeechSynthesisUtterance(text);
    const lang = (result && result.target_language) || ui.targetLang.value;
    utter.lang = bcp47(lang);

    const p = (result && result.prosody) || {};
    utter.rate = p.rate || 1;
    utter.pitch = p.pitch || 1;

    const voice = pickVoice(utter.lang);
    if (voice) utter.voice = voice;
    window.speechSynthesis.speak(utter);
  }

  function pickVoice(tag) {
    const voices = window.speechSynthesis.getVoices() || [];
    const base = tag.split("-")[0];
    return (
      voices.find((v) => v.lang === tag) ||
      voices.find((v) => v.lang.startsWith(base)) ||
      null
    );
  }

  const BCP47 = {
    bn: "bn-IN", hi: "hi-IN", ta: "ta-IN", te: "te-IN", kn: "kn-IN",
    ml: "ml-IN", mr: "mr-IN", gu: "gu-IN", pa: "pa-IN", en: "en-US",
    de: "de-DE", fr: "fr-FR", es: "es-ES", it: "it-IT", pt: "pt-BR",
    ja: "ja-JP",
  };
  function bcp47(code) {
    return BCP47[code] || code || "en-US";
  }

  // ------------------------------------------------------------------- ASR

  let recognition = null;

  function setupSpeechRecognition() {
    const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Ctor) {
      // iOS Safari lands here. The socket path sends audio to the server
      // instead, if a backend is installed.
      ui.asrHint.textContent = "Speech input unavailable in this browser — type instead";
      ui.micBtn.disabled = true;
      return;
    }

    recognition = new Ctor();
    recognition.continuous = false;
    recognition.interimResults = true;

    recognition.addEventListener("result", (event) => {
      let finalText = "";
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const chunk = event.results[i];
        if (chunk.isFinal) finalText += chunk[0].transcript;
        else interim += chunk[0].transcript;
      }
      ui.sourceText.value = (finalText || interim).trim();
      if (finalText) translate();
      else sendPartial(ui.sourceText.value);
    });

    recognition.addEventListener("end", () => setListening(false));
    recognition.addEventListener("error", (e) => {
      setListening(false);
      if (e.error !== "aborted" && e.error !== "no-speech") {
        showWarning(`Microphone error: ${e.error}`);
      }
    });

    ui.asrHint.textContent = "Ctrl/⌘ + Enter to translate";
  }

  function toggleMic() {
    if (!recognition) return;
    if (state.listening) {
      recognition.stop();
      return;
    }
    recognition.lang = bcp47(ui.sourceLang.value || "en");
    try {
      recognition.start();
      setListening(true);
    } catch (_) {
      /* already started */
    }
  }

  function setListening(on) {
    state.listening = on;
    ui.micBtn.dataset.listening = String(on);
    ui.micLabel.textContent = on ? "Listening…" : "Speak";
  }

  // ---------------------------------------------------------------- socket

  let socket = null;

  function setupSocket() {
    if (typeof io === "undefined") return;
    try {
      socket = io();
      socket.on("connect", () => setStatus("Ready", "ready"));
      socket.on("disconnect", () => setStatus("Offline", "error"));
      socket.on("translation_result", (data) => {
        render(data);
        setStatus("Ready", "ready");
      });
      socket.on("translation_partial", (data) => {
        // Anything but the newest guess has been overtaken by more speech.
        if (data.seq !== state.partial.seq) return;
        renderPartial(data);
      });
      socket.on("translation_error", (data) => showWarning(data.message));
    } catch (_) {
      /* REST still works without a socket */
    }
  }

  /*
   * Translate what is being said while it is still being said (blueprint 5.2).
   *
   * The browser hands back interim transcripts a few hundred milliseconds in,
   * and this used to drop them on the floor until the speaker stopped. Now
   * each one is translated speculatively and shown greyed out, so the answer
   * is on screen before the sentence ends — and because the register layer is
   * a string pass, the preview is already at the right politeness level rather
   * than a raw MT dump that changes tone when it settles.
   *
   * Sent over the socket rather than as a request, because the persistent
   * connection is the single biggest real-world latency win in the blueprint:
   * a cold TLS handshake costs more than the translation does.
   */
  function sendPartial(text) {
    if (!socket || !text || state.busy) return;
    const now = Date.now();
    if (text === state.partial.text) return;          // ASR repeated itself
    if (now - state.partial.sentAt < 300) return;     // it revises constantly
    if (text.length < 8) return;                      // too little to translate

    state.partial.text = text;
    state.partial.sentAt = now;
    state.partial.seq += 1;
    socket.emit("translate_partial", {
      text,
      seq: state.partial.seq,
      source_lang: ui.sourceLang.value || null,
      target_lang: ui.targetLang.value,
      register: state.register,
      addressee: state.addressee || null,
      soften: ui.soften.checked,
      keep_english: ui.keepEnglish.checked,
    });
  }

  /*
   * Show a guess. Deliberately less than render(): no ladder, no rule trace,
   * no timings, and the Play button stays disabled — speaking a sentence that
   * is about to be corrected is worse than staying quiet.
   */
  function renderPartial(data) {
    if (!data.translated_text || state.busy) return;
    state.partial.showing = true;
    ui.resultPanel.hidden = false;
    ui.outputText.textContent = data.translated_text;
    ui.outputText.lang = data.target_language || "";
    ui.outputText.dataset.partial = "true";
    // A guess is revised every few hundred milliseconds. Narrating each
    // revision would make the page unusable with a screen reader, so the
    // region is marked busy until the sentence settles.
    ui.outputText.setAttribute("aria-busy", "true");
    ui.speakBtn.disabled = true;
    ui.badgeRegister.textContent =
      `${data.register_name} · still speaking…`;
    ui.badgeEngine.textContent = "";
    ui.badgeTiming.textContent = "";
  }

  function clearPartial() {
    state.partial.showing = false;
    state.partial.text = "";
    // Any in-flight guess is now stale: its sequence number no longer matches.
    state.partial.seq += 1;
    delete ui.outputText.dataset.partial;
    ui.outputText.setAttribute("aria-busy", "false");
  }

  async function refreshPhrasebook() {
    try {
      const res = await fetch("/api/phrasebook");
      const data = await res.json();
      ui.phrasebookStats.textContent =
        `${data.phrases} phrase${data.phrases === 1 ? "" : "s"} cached`;
    } catch (_) {
      ui.phrasebookStats.textContent = "";
    }
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* app works fine without it; only offline caching is lost */
    });
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
