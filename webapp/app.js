"use strict";

// ── Elements ──────────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const messages = $("messages");
const activity = $("activity");
const textInput = $("textInput");
const sendBtn = $("sendBtn");
const micBtn = $("micBtn");
const statusDot = $("statusDot");
const statusText = $("statusText");
const dangerBadge = $("dangerBadge");
const modelInfo = $("modelInfo");
const fileList = $("fileList");
const factList = $("factList");
const dropZone = $("dropZone");
const fileInput = $("fileInput");

let ws = null;
let currentAssistantBubble = null;

// Voice / wake-word state
let wakeWords = ["hey jarvis", "jarvis"];
let wakeEnabled = false; // hands-free "Hey Jarvis" mode
let armed = false; // heard the wake word; next utterance is the command
let speaking = false; // TTS is talking — ignore the mic so it can't hear itself

// ── Chat rendering ────────────────────────────────────────────────────────────
function addBubble(role, text) {
  const div = document.createElement("div");
  div.className = `bubble ${role}`;
  const who = document.createElement("div");
  who.className = "who";
  who.textContent = role === "user" ? "🧑 You" : "🤖 Jarvis";
  const body = document.createElement("div");
  body.textContent = text;
  div.append(who, body);
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return body;
}

function setActivity(text) {
  if (!text) {
    activity.classList.add("hidden");
    activity.textContent = "";
  } else {
    activity.classList.remove("hidden");
    activity.textContent = text;
  }
}

function speak(text) {
  if (!("speechSynthesis" in window)) return;
  const utter = new SpeechSynthesisUtterance(text);
  speaking = true;
  recognizerStop(); // pause listening so the mic doesn't pick up Jarvis
  utter.onend = () => {
    speaking = false;
    if (wakeEnabled) recognizerStart(); // resume hands-free listening
  };
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utter);
}

const TOOL_LABELS = {
  get_time: "🕒 checking the time",
  web_search: "🌐 searching the web",
  fetch_url: "📰 reading a page",
  open_chrome: "🧭 opening Chrome",
  open_in_browser: "🧭 opening a tab",
  read_file: "📄 reading a file",
  write_file: "✍️ writing a file",
  summarize_file: "📄 reading a file",
  remember_fact: "🧠 saving to memory",
  recall_fact: "🧠 recalling memory",
};

// ── WebSocket streaming ───────────────────────────────────────────────────────
function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/stream`);
  ws.onopen = () => setStatus(true, "Ready");
  ws.onclose = () => {
    setStatus(false, "Disconnected — retrying…");
    setTimeout(connectWS, 2000);
  };
  ws.onmessage = (ev) => handleEvent(JSON.parse(ev.data));
}

function handleEvent(event) {
  if (event.type === "tool") {
    setActivity((TOOL_LABELS[event.name] || `🔧 ${event.name}`) + "…");
  } else if (event.type === "tool_result") {
    // keep the activity line; result is folded into the final answer
  } else if (event.type === "final") {
    setActivity("");
    if (currentAssistantBubble) {
      currentAssistantBubble.textContent = event.text;
    } else {
      addBubble("assistant", event.text);
    }
    currentAssistantBubble = null;
    speak(event.text);
    loadFacts();
    loadFiles();
  }
}

function sendMessage(text) {
  text = (text || "").trim();
  if (!text) return;
  addBubble("user", text);
  currentAssistantBubble = addBubble("assistant", "…");
  setActivity("🤖 thinking…");
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ message: text }));
  } else {
    // HTTP fallback if the socket is down
    fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    })
      .then((r) => r.json())
      .then((d) => handleEvent({ type: "final", text: d.reply }));
  }
}

function setStatus(on, text) {
  statusDot.classList.toggle("on", on);
  statusText.textContent = text;
}

// ── Voice input + wake word (Web Speech API) ──────────────────────────────────
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const wakeBtn = $("wakeBtn");
let recognition = null;

if (SR) {
  recognition = new SR();
  recognition.lang = "en-US";
  recognition.continuous = true; // keep listening for the wake word
  recognition.interimResults = false;
  recognition.onresult = onSpeech;
  recognition.onerror = (e) => {
    if (e.error === "not-allowed") {
      setWake(false);
      setStatus(false, "Mic blocked — allow microphone access");
    }
  };
  // Browsers stop continuous recognition periodically; restart it while active.
  recognition.onend = () => {
    if (wakeEnabled && !speaking) recognizerStart();
  };
} else {
  micBtn.title = "Voice input not supported in this browser";
  wakeBtn.disabled = true;
}

function recognizerStart() {
  try {
    recognition.start();
  } catch (e) {
    /* already started */
  }
}
function recognizerStop() {
  try {
    recognition.stop();
  } catch (e) {
    /* already stopped */
  }
}

// Strip a leading wake phrase and return the command after it (or null).
function stripWake(text) {
  for (const w of wakeWords) {
    const i = text.indexOf(w);
    if (i !== -1) {
      return text
        .slice(i + w.length)
        .replace(/^[\s,.!?:;-]+/, "")
        .trim();
    }
  }
  return null;
}

function onSpeech(e) {
  if (speaking) return; // ignore our own TTS
  const text = e.results[e.results.length - 1][0].transcript.trim().toLowerCase();
  if (!text) return;

  const afterWake = stripWake(text);
  if (afterWake !== null) {
    // Heard "Hey Jarvis ..."
    if (afterWake) {
      sendMessage(afterWake); // command was in the same breath
    } else {
      armed = true; // just the wake word — capture the next utterance
      setStatus(true, "🎙️ Listening — say your command");
    }
    return;
  }

  if (armed) {
    armed = false;
    sendMessage(text);
    if (!wakeEnabled) recognizerStop();
  }
  // Otherwise: speech not addressed to Jarvis — ignore it.
}

function setWake(on) {
  wakeEnabled = on;
  armed = false;
  wakeBtn.textContent = on ? "🎙️ Hey Jarvis: ON" : "🎙️ Hey Jarvis: OFF";
  wakeBtn.classList.toggle("active", on);
  if (on) {
    recognizerStart();
    setStatus(true, 'Hands-free — say "Hey Jarvis"');
  } else {
    recognizerStop();
    setStatus(true, "Ready");
  }
}

wakeBtn.addEventListener("click", () => setWake(!wakeEnabled));

// Manual mic: capture a single command now (no wake word needed).
micBtn.addEventListener("click", () => {
  if (!recognition) return;
  armed = true;
  setStatus(true, "🎙️ Listening…");
  recognizerStart();
});

// ── Files ─────────────────────────────────────────────────────────────────────
async function loadFiles() {
  const res = await fetch("/files").then((r) => r.json());
  fileList.innerHTML = "";
  for (const f of res.files) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = `/files/${encodeURIComponent(f.name)}`;
    a.textContent = f.name;
    a.className = "name";
    const ask = document.createElement("button");
    ask.textContent = "ask";
    ask.title = "Ask Jarvis about this file";
    ask.onclick = () => sendMessage(`Summarize the file ${f.name}`);
    li.append(a, ask);
    fileList.appendChild(li);
  }
}

async function uploadFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  await fetch("/files/upload", { method: "POST", body: fd });
  loadFiles();
}

dropZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) uploadFile(fileInput.files[0]);
});
["dragover", "dragenter"].forEach((ev) =>
  dropZone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropZone.classList.add("hover");
  })
);
["dragleave", "drop"].forEach((ev) =>
  dropZone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropZone.classList.remove("hover");
  })
);
dropZone.addEventListener("drop", (e) => {
  if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
});

// ── Memory ────────────────────────────────────────────────────────────────────
async function loadFacts() {
  const res = await fetch("/memory/facts").then((r) => r.json());
  factList.innerHTML = "";
  for (const f of res.facts) {
    const li = document.createElement("li");
    const kv = document.createElement("div");
    kv.className = "kv name";
    kv.innerHTML = `<span class="k">${f.key}</span><span class="v">${f.value}</span>`;
    const del = document.createElement("button");
    del.textContent = "✕";
    del.onclick = async () => {
      await fetch(`/memory/facts/${encodeURIComponent(f.key)}`, { method: "DELETE" });
      loadFacts();
    };
    li.append(kv, del);
    factList.appendChild(li);
  }
}

$("clearHistoryBtn").addEventListener("click", async () => {
  await fetch("/memory/clear", { method: "POST" });
  messages.innerHTML = "";
});

$("toggleSidebar").addEventListener("click", () =>
  $("sidebar").classList.toggle("collapsed")
);

// ── Wire up & boot ────────────────────────────────────────────────────────────
sendBtn.addEventListener("click", () => {
  sendMessage(textInput.value);
  textInput.value = "";
});
textInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    sendMessage(textInput.value);
    textInput.value = "";
  }
});

async function boot() {
  try {
    const h = await fetch("/health").then((r) => r.json());
    modelInfo.textContent = `${h.provider} · ${h.model}`;
    if (h.dangerous_tools_enabled) dangerBadge.classList.remove("hidden");
    if (Array.isArray(h.wake_words) && h.wake_words.length) {
      wakeWords = h.wake_words.map((w) => w.toLowerCase());
    }
  } catch (e) {
    /* ignore */
  }
  connectWS();
  loadFiles();
  loadFacts();
}
boot();
