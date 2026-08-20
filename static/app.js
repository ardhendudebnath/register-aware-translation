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
    convo: {
      id: null,
      a: { register: "auto" },
      b: { register: "auto" },
      speaker: "",
      shown: 0,   // shifts already announced, so they are not repeated
    },
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

    updateLevelHint();
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
      if (state.lastResult) relevel();
    });
    ui.swapLangs.addEventListener("click", swapLanguages);
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
    // same base rather than compounding edits.
    if (!opts.keepLadder) {
      data.mt_base = data.ladder && data.ladder.Casual
        ? data.ladder.Casual
        : data.translated_text;
    } else if (state.lastResult) {
      data.mt_base = state.lastResult.mt_base;
      data.ladder = state.lastResult.ladder;
    }
    state.lastResult = data;

    ui.resultPanel.hidden = false;
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

    if (data.detected_register_name) {
      const slang = (data.detected_slang || []).map((s) => s.term);
      ui.detectedRegister.textContent =
        `You spoke in ${data.detected_register_name}` +
        (slang.length ? ` · slang: ${slang.join(", ")}` : "");
    } else {
      ui.detectedRegister.textContent = "";
    }

    renderTrace(data.edits || []);
    if (!opts.keepLadder) renderLadder(data.ladder || {});
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

  function renderLadder(ladder) {
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
          `<span class="txt" dir="auto">${esc(text)}</span>` +
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
    const names = Object.keys(convo.participants || {});
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
        const rows = [
          `<li data-side="${side.get(turn.speaker) || "a"}">` +
            `<p class="said">${esc(turn.speaker)}: ${esc(turn.text)}</p>` +
            (echoed
              ? `<p class="heard" dir="auto">${esc(turn.translated)}</p>`
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

  function setupSocket() {
    if (typeof io === "undefined") return;
    try {
      const socket = io();
      socket.on("connect", () => setStatus("Ready", "ready"));
      socket.on("disconnect", () => setStatus("Offline", "error"));
      socket.on("translation_result", (data) => {
        render(data);
        setStatus("Ready", "ready");
      });
      socket.on("translation_error", (data) => showWarning(data.message));
    } catch (_) {
      /* REST still works without a socket */
    }
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
