"use strict";

const $ = (id) => document.getElementById(id);

const STEPS = [
  { id: "prompt", title: "gui.tab_prompt", hint: "gui.prompt_hint", action: "gui.analyze" },
  { id: "analysis", title: "gui.issues_label", hint: "gui.analysis_hint", action: "gui.rewrite" },
  { id: "questions", title: "gui.questions_label", hint: "gui.questions_hint", action: "gui.rewrite" },
  { id: "result", title: "gui.result_label", hint: "gui.result_hint", action: "" },
  { id: "sessions", title: "web.sessions", hint: "web.sessions_hint", action: "" },
];

const state = { lang: "ru", languages: ["ru", "en"], version: "", provider: "", model: "", strings: {} };
let current = "prompt";
let session = null;
let outcome = null;
let busy = false;

function t(key, vars) {
  let text = Object.prototype.hasOwnProperty.call(state.strings, key) ? state.strings[key] : "";
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      text = text.split("{" + name + "}").join(String(value));
    }
  }
  return text;
}

async function post(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = {};
  try {
    data = await response.json();
  } catch (error) {
    data = {};
  }
  if (!response.ok) {
    const problem = data.error || {};
    const parts = [problem.message || response.statusText];
    if (problem.hint) parts.push(problem.hint);
    throw new Error(parts.join(" — "));
  }
  return data;
}

function notice(title, body) {
  $("notice-title").textContent = title;
  $("notice-body").textContent = body || "";
  $("notice").hidden = false;
}

function clearNotice() {
  $("notice").hidden = true;
}

function setStatus(text) {
  $("status").textContent = text;
}

function setBusy(value, message) {
  busy = value;
  document.body.classList.toggle("is-busy", value);
  $("primary").disabled = value || !primaryIsUsable();
  if (value && message) setStatus(message);
}

function primaryIsUsable() {
  if (current === "prompt") return $("prompt").value.trim().length > 0;
  if (current === "analysis" || current === "questions") return Boolean(session);
  return false;
}

function applyStrings() {
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  $("provider").textContent = state.provider + (state.model && state.model !== "-" ? " / " + state.model : "");
  $("version").textContent = state.version;
  renderHead();
  setStatus(t("gui.ready"));
}

function renderHead() {
  const meta = STEPS.find((item) => item.id === current);
  $("step-index").textContent = String(STEPS.indexOf(meta) + 1);
  $("step-title").textContent = t(meta.title);
  $("step-hint").textContent = t(meta.hint);
  const primary = $("primary");
  primary.textContent = meta.action ? t(meta.action) : t("gui.restart");
  primary.hidden = current === "result" || current === "sessions";
  primary.disabled = busy || !primaryIsUsable();
  $("restart").hidden = !session;
}

function setStep(next) {
  current = next;
  for (const item of STEPS) {
    $("panel-" + item.id).hidden = item.id !== next;
  }
  document.querySelectorAll(".step").forEach((node) => {
    node.classList.toggle("is-current", node.dataset.goto === next);
    node.disabled = !stepEnabled(node.dataset.goto);
  });
  renderHead();
  if (next === "sessions") loadSessions();
}

function stepEnabled(id) {
  if (id === "prompt" || id === "sessions") return true;
  if (id === "analysis" || id === "questions") return Boolean(session);
  return Boolean(outcome);
}

function renderAnalysis(data) {
  const analysis = data.analysis || {};
  $("score").textContent = String(analysis.score ?? "–");
  $("summary").textContent = analysis.summary || "";
  const list = $("issues");
  list.textContent = "";
  const issues = analysis.issues || [];
  issues.forEach((issue, index) => {
    const li = document.createElement("li");
    const head = document.createElement("p");
    head.className = "issue-head";
    head.innerHTML =
      '<span class="issue-no">' + String(index + 1).padStart(2, "0") + "</span>" +
      '<span class="issue-sev sev-' + issue.severity + '">' + escapeHtml(t("severity." + issue.severity)) + "</span>" +
      '<span class="issue-cat">' + escapeHtml(t("category." + issue.category)) + "</span>";
    const title = document.createElement("p");
    title.className = "issue-title";
    title.textContent = issue.title;
    li.append(head, title);
    if (issue.detail) {
      const detail = document.createElement("p");
      detail.className = "issue-detail";
      detail.textContent = issue.detail;
      li.append(detail);
    }
    if (issue.evidence) {
      const evidence = document.createElement("p");
      evidence.className = "issue-evidence";
      evidence.textContent = issue.evidence;
      li.append(evidence);
    }
    list.append(li);
  });
  $("issues-empty").hidden = issues.length > 0;
}

function renderQuestions(questions) {
  const list = $("questions");
  list.textContent = "";
  questions.forEach((question, index) => {
    const li = document.createElement("li");
    const head = document.createElement("div");
    head.className = "q-head";
    const no = document.createElement("span");
    no.className = "q-no";
    no.textContent = String(index + 1).padStart(2, "0");
    const text = document.createElement("span");
    text.className = "q-text";
    text.textContent = question.text;
    head.append(no, text);
    li.append(head);
    if (question.why) {
      const why = document.createElement("p");
      why.className = "q-why";
      why.textContent = question.why;
      li.append(why);
    }
    const input = document.createElement("input");
    input.className = "q-input";
    input.type = "text";
    input.dataset.qid = question.id;
    input.setAttribute("aria-label", question.text);
    if (question.options && question.options.length) {
      const options = document.createElement("div");
      options.className = "q-options";
      question.options.forEach((option) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "chip";
        chip.textContent = option;
        chip.addEventListener("click", () => {
          input.value = option;
          input.focus();
        });
        options.append(chip);
      });
      li.append(options);
    }
    li.append(input);
    list.append(li);
  });
  $("questions-empty").hidden = questions.length > 0;
}

function renderResult(data) {
  const rewrite = data.rewrite || {};
  const badge = $("mode");
  badge.textContent = t("run.mode_label", { mode: t("run.mode." + data.mode) });
  badge.className = "badge is-" + data.mode;
  $("draft").textContent = rewrite.improved_prompt || "";
  const list = $("changes");
  list.textContent = "";
  (rewrite.changes || []).forEach((change) => {
    const li = document.createElement("li");
    li.textContent = change;
    list.append(li);
  });
}

async function runPrimary() {
  if (busy) return;
  if (current === "prompt") return analyze();
  if (current === "analysis" || current === "questions") return rewrite();
  return restart();
}

async function analyze() {
  const prompt = $("prompt").value.trim();
  if (!prompt) {
    notice(t("gui.error"), t("gui.no_prompt"));
    return;
  }
  clearNotice();
  setBusy(true, t("run.analyzing", { provider: state.provider }));
  try {
    const data = await post("/api/analyze", { prompt: prompt, lang: state.lang });
    session = data;
    outcome = null;
    $("restart").hidden = false;
    renderAnalysis(data);
    renderQuestions(data.questions || []);
    document.querySelectorAll(".step").forEach((node) => {
      node.disabled = !stepEnabled(node.dataset.goto);
    });
    if (data.warnings && data.warnings.length) {
      notice(t("gui.warning"), data.warnings[data.warnings.length - 1]);
    }
    setStep(data.questions && data.questions.length ? "questions" : "analysis");
    setStatus(t("gui.analysis_ready"));
  } catch (error) {
    notice(t("gui.error"), error.message);
    setStatus(t("gui.error"));
  } finally {
    setBusy(false);
  }
}

async function rewrite() {
  if (!session) return;
  const answers = {};
  document.querySelectorAll("#questions .q-input").forEach((node) => {
    answers[node.dataset.qid] = node.value;
  });
  clearNotice();
  setBusy(true, t("run.rewriting"));
  try {
    const data = await post("/api/rewrite", { id: session.id, answers: answers });
    outcome = data;
    renderResult(data);
    setStep("result");
    setStatus(t("run.saved", { path: data.saved || "" }));
  } catch (error) {
    notice(t("gui.error"), error.message);
    setStatus(t("gui.error"));
  } finally {
    setBusy(false);
    document.querySelectorAll(".step").forEach((node) => {
      node.disabled = !stepEnabled(node.dataset.goto);
    });
  }
}

function restart() {
  session = null;
  outcome = null;
  clearNotice();
  $("prompt").value = "";
  $("issues").textContent = "";
  $("questions").textContent = "";
  $("draft").textContent = "";
  $("changes").textContent = "";
  $("score").textContent = "–";
  $("summary").textContent = "";
  $("restart").hidden = true;
  setStep("prompt");
  setStatus(t("gui.ready"));
  $("prompt").focus();
}

async function copyDraft() {
  const text = $("draft").textContent;
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    setStatus(t("gui.copied"));
  } catch (error) {
    setStatus(t("gui.error") + ": " + error.message);
  }
}

function downloadDraft() {
  const text = $("draft").textContent;
  if (!text) return;
  const format = $("export-format").value || "md";
  const changes = Array.from(document.querySelectorAll("#changes li")).map((node) =>
    node.textContent.replace(/^- /, "")
  );
  let body;
  if (format === "json") {
    body = JSON.stringify({ prompt: $("prompt").value, improved_prompt: text, changes: changes }, null, 2) + "\n";
  } else if (format === "txt") {
    body = text + (changes.length ? "\n\n" + t("gui.changes_label") + "\n" + changes.map((c) => "- " + c).join("\n") : "") + "\n";
  } else {
    body =
      "# PromptWizard\n\n" +
      text +
      (changes.length ? "\n\n## " + t("gui.changes_label") + "\n\n" + changes.map((c) => "- " + c).join("\n") : "") +
      "\n";
  }
  const types = { json: "application/json", txt: "text/plain", md: "text/markdown" };
  const blob = new Blob([body], { type: (types[format] || "text/plain") + ";charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "promptwizard-" + ((outcome && outcome.id) || "draft") + "." + format;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}

function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = String(value);
  return node.innerHTML;
}

async function loadState(lang, attempt) {
  const tries = attempt || 0;
  let data;
  try {
    const response = await fetch("/api/state?lang=" + encodeURIComponent(lang));
    data = await response.json();
  } catch (error) {
    if (tries < 3) {
      setTimeout(() => loadState(lang, tries + 1), 700 * (tries + 1));
      return;
    }
    notice("PromptWizard", "Could not load the interface strings from the local server. Reload the window.");
    return;
  }
  if (!data || !data.strings || !Object.keys(data.strings).length) {
    if (tries < 3) {
      setTimeout(() => loadState(lang, tries + 1), 700 * (tries + 1));
      return;
    }
    notice("PromptWizard", "The local server sent no interface strings. Reload the window.");
    return;
  }
  state.lang = data.lang;
  state.languages = data.languages || ["ru"];
  state.version = data.version;
  state.provider = data.provider;
  state.model = data.model;
  state.strings = data.strings || {};
  state.settings = data.settings || {};
  state.themes = data.themes || ["light", "dark"];
  const select = $("lang");
  select.textContent = "";
  state.languages.forEach((code) => {
    const option = document.createElement("option");
    option.value = code;
    option.textContent = code.toUpperCase();
    option.selected = code === state.lang;
    select.append(option);
  });
  $("prompt").placeholder = t("gui.prompt_placeholder");
  fillSettings();
  applyStrings();
  if (session) renderAnalysis(session);
  if (session) renderQuestions(session.questions || []);
  if (outcome) renderResult(outcome);
}

async function loadSessions() {
  const list = $("session-list");
  list.textContent = "";
  try {
    const response = await fetch("/api/sessions?limit=40");
    const data = await response.json();
    (data.sessions || []).forEach((record) => {
      const li = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "session-row";
      const head = document.createElement("span");
      head.className = "session-meta";
      head.textContent =
        record.finished_at.slice(0, 19).replace("T", " ") +
        "  ·  " + record.provider + "/" + record.model +
        "  ·  " + t("run.score", { score: record.score });
      const body = document.createElement("span");
      body.className = "session-prompt";
      body.textContent = record.prompt;
      button.append(head, body);
      button.addEventListener("click", () => openSession(record.id));
      li.append(button);
      list.append(li);
    });
    $("sessions-empty").hidden = (data.sessions || []).length > 0;
  } catch (error) {
    setStatus(error.message);
  }
}

async function openSession(id) {
  try {
    const response = await fetch("/api/sessions/" + encodeURIComponent(id));
    if (!response.ok) throw new Error(t("gui.error"));
    const data = await response.json();
    outcome = data;
    session = null;
    $("prompt").value = "";
    renderResult(data);
    document.querySelectorAll(".step").forEach((node) => {
      node.disabled = !stepEnabled(node.dataset.goto);
    });
    setStep("result");
    setStatus(t("web.opened_session", { id: data.id }));
  } catch (error) {
    setStatus(error.message);
  }
}

function wire() {
  $("primary").addEventListener("click", runPrimary);
  $("restart").addEventListener("click", restart);
  $("load-file").addEventListener("click", () => $("file-input").click());
  $("file-input").addEventListener("change", async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    $("prompt").value = await file.text();
    if (current === "prompt") $("primary").disabled = busy || !primaryIsUsable();
    setStatus(file.name);
    event.target.value = "";
  });
  $("copy").addEventListener("click", copyDraft);
  $("download").addEventListener("click", downloadDraft);
  $("prompt").addEventListener("input", () => {
    if (current === "prompt") $("primary").disabled = busy || !primaryIsUsable();
  });
  $("lang").addEventListener("change", (event) => loadState(event.target.value));
  document.querySelectorAll(".step").forEach((node) => {
    node.addEventListener("click", () => {
      if (!node.disabled) setStep(node.dataset.goto);
    });
  });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      runPrimary();
    }
  });
}

function applyTheme(theme) {
  const chosen = state.themes.includes(theme) ? theme : "light";
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = chosen === "auto" ? (prefersDark ? "dark" : "light") : chosen;
}

function applyTypography() {
  const settings = state.settings || {};
  const size = Number(settings.font_size) || 15;
  document.documentElement.style.setProperty("--base-size", size + "px");
  const family = (settings.font || "").trim();
  if (family) {
    document.documentElement.style.setProperty(
      "--sans",
      '"' + family + '", "Segoe UI", "Helvetica Neue", Arial, sans-serif'
    );
  } else {
    document.documentElement.style.removeProperty("--sans");
  }
}

function fillSettings() {
  const settings = state.settings || {};
  applyTheme(settings.theme);
  $("theme").value = settings.theme || "light";
  const select = $("provider-select");
  select.textContent = "";
  Object.keys(settings.providers || {}).sort().forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    option.selected = name === settings.provider;
    select.append(option);
  });
  $("model-input").value = settings.model || "";
  const presetSelect = $("preset");
  presetSelect.textContent = "";
  const none = document.createElement("option");
  none.value = "";
  none.textContent = t("web.preset_none");
  presetSelect.append(none);
  Object.entries(settings.presets || {}).forEach(([name, preset]) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = preset.alias || name;
    option.title = preset.tooltip || "";
    presetSelect.append(option);
  });
  $("ask-questions").checked = Number(settings.max_questions) > 0;
  $("set-max-questions").value = settings.max_questions;
  const fontSelect = $("font");
  fontSelect.textContent = "";
  (settings.fonts || [""]).forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name ? name : t("web.font_default");
    option.selected = name === (settings.font || "");
    fontSelect.append(option);
  });
  $("font-size").value = settings.font_size || 15;
  const auto = settings.autostart || {};
  $("autostart").checked = Boolean(auto.enabled);
  $("autostart").disabled = !auto.supported;
  $("autostart-note").textContent = auto.supported
    ? (auto.enabled && auto.command ? auto.command : t("web.autostart_hint"))
    : t("web.autostart_unsupported");
  $("set-max-questions").value = settings.max_questions;
  $("set-max-questions").value = settings.max_questions;
  $("set-temperature").value = settings.temperature;
  $("set-max-tokens").value = settings.max_tokens;
  applyTypography();
  $("config-path").textContent = settings.path || "";
  loadModels(settings.provider);
}

async function loadModels(provider) {
  const note = $("models-note");
  try {
    const response = await fetch("/api/models?provider=" + encodeURIComponent(provider || ""));
    const data = await response.json();
    const list = $("model-list");
    list.textContent = "";
    (data.models || []).forEach((name) => {
      const option = document.createElement("option");
      option.value = name;
      list.append(option);
    });
    if (!data.note && data.current) $("model-input").value = $("model-input").value || data.current;
    note.textContent = data.note || t(data.source === "provider" ? "web.models_from" : "web.models_builtin");
  } catch (error) {
    note.textContent = error.message;
  }
}

async function saveSettings() {
  const payload = {
    theme: $("theme").value,
    provider: $("provider-select").value,
    model: $("model-input").value.trim(),
    font: $("font").value,
    font_size: Number($("font-size").value) || 15,
    max_questions: Number($("set-max-questions").value),
    temperature: Number($("set-temperature").value),
    max_tokens: Number($("set-max-tokens").value),
  };
  try {
    const data = await post("/api/settings", payload);
    state.settings = data.settings || state.settings;
    state.strings = data.strings || state.strings;
    fillSettings();
    applyStrings();
    $("settings-note").textContent = t("web.saved_settings");
  } catch (error) {
    $("settings-note").textContent = error.message;
  }
}

async function addCustomProvider() {
  const name = $("custom-name").value.trim();
  const base = $("custom-base").value.trim();
  const model = $("custom-model").value.trim();
  const keyEnv = $("custom-key").value.trim();
  const note = $("custom-note");
  if (!name || !base || !model) {
    note.textContent = t("web.custom_required");
    return;
  }
  const providers = {};
  providers[name] = { base_url: base, model: model, api_key_env: keyEnv, kind: "openai_compatible" };
  try {
    const data = await post("/api/settings", { providers: providers, provider: name, model: model });
    state.settings = data.settings || state.settings;
    state.strings = data.strings || state.strings;
    fillSettings();
    note.textContent = t("web.provider_added");
  } catch (error) {
    note.textContent = error.message;
  }
}

function wireSettings() {
  $("open-settings").addEventListener("click", () => {
    $("drawer").hidden = false;
  });
  $("close-settings").addEventListener("click", () => {
    $("drawer").hidden = true;
  });
  $("theme").addEventListener("change", (event) => applyTheme(event.target.value));
  $("font").addEventListener("change", () => {
    state.settings = Object.assign({}, state.settings, { font: $("font").value });
    applyTypography();
  });
  $("font-size").addEventListener("input", () => {
    state.settings = Object.assign({}, state.settings, { font_size: Number($("font-size").value) || 15 });
    applyTypography();
  });
  $("autostart").addEventListener("change", async () => {
    try {
      const data = await post("/api/autostart", { enabled: $("autostart").checked });
      $("autostart").checked = Boolean(data.enabled);
      $("autostart-note").textContent = data.enabled ? (data.command || t("web.autostart_on")) : t("web.autostart_off");
    } catch (error) {
      $("autostart-note").textContent = error.message;
    }
  });
  $("ask-questions").addEventListener("change", () => {
    $("set-max-questions").value = $("ask-questions").checked ? 6 : 0;
  });
  $("preset").addEventListener("change", async () => {
    const name = $("preset").value;
    if (!name) return;
    const preset = (state.settings.presets || {})[name];
    if (!preset) return;
    $("provider-select").value = preset.provider || $("provider-select").value;
    $("model-input").value = preset.model || $("model-input").value;
    await saveSettings();
    $("settings-note").textContent = t("web.preset_applied", { name: preset.alias || name });
  });
  $("provider-select").addEventListener("change", (event) => loadModels(event.target.value));
  $("settings-save").addEventListener("click", saveSettings);
  $("custom-save").addEventListener("click", addCustomProvider);
  $("open-config").addEventListener("click", async () => {
    try {
      const data = await post("/api/config/open", { launch: true });
      $("settings-note").textContent = data.path || "";
    } catch (error) {
      $("settings-note").textContent = error.message;
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      $("drawer").hidden = true;
      return;
    }
    if (!(event.ctrlKey || event.metaKey)) return;
    if (event.key === "o" || event.key === "O") {
      event.preventDefault();
      $("file-input").click();
      return;
    }
    if (event.key === "s" || event.key === "S") {
      if ($("draft").textContent) {
        event.preventDefault();
        downloadDraft();
      }
      return;
    }
    if (event.key === ",") {
      event.preventDefault();
      $("drawer").hidden = false;
    }
  });
}

wireSettings();
wire();
loadState("ru");
setStep("prompt");
