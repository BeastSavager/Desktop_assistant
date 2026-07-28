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
const wakeBtn = $("wakeBtn");
const clearHistoryBtn = $("clearHistoryBtn");

// Layout & Custom Redesign Elements
const leftSidebar = $("leftSidebar");
const rightSidebar = $("rightSidebar");
const toggleLeftSidebar = $("toggleLeftSidebar");
const expandLeftSidebar = $("expandLeftSidebar");
const toggleRightSidebar = $("toggleRightSidebar");
const toggleRightSidebarClose = $("toggleRightSidebarClose");
const welcomeScreen = $("welcomeScreen");
const chatPane = $("chatPane");
const newChatBtn = $("newChatBtn");
const historyList = $("historyList");
const chatSearch = $("chatSearch");
const openSettingsBtn = $("openSettingsBtn");
const settingsModal = $("settingsModal");
const closeSettingsModalBtn = $("closeSettingsModalBtn");
const commandPalette = $("commandPalette");
const paletteSearch = $("paletteSearch");
const paletteResults = $("paletteResults");
const voiceOverlay = $("voiceOverlay");
const closeVoiceOverlayBtn = $("closeVoiceOverlayBtn");
const voiceOverlayStatus = $("voiceOverlayStatus");

// Settings panes elements
const settingsTabs = document.querySelectorAll(".settings-tabs .tab-item");
const settingsPanes = document.querySelectorAll(".settings-panes .settings-pane");
const settingsTabTitle = $("settingsTabTitle");
const voiceSelect = $("voiceSelect");
const settingSpeakToggle = $("settingSpeakToggle");
const settingWakeToggle = $("settingWakeToggle");
const settingsProvider = $("settingsProvider");
const cloudModelGroup = $("cloudModelGroup");
const settingsApiKey = $("settingsApiKey");
const settingsBaseUrl = $("settingsBaseUrl");
const settingsModelName = $("settingsModelName");
const dangerousToolsSwitch = $("dangerousToolsSwitch");
const tempSlider = $("tempSlider");
const tempValue = $("tempValue");
const modelSelector = $("modelSelector");

// System Context Widget elements
const cpuDial = $("cpuDial");
const cpuText = $("cpuText");
const ramDial = $("ramDial");
const ramText = $("ramText");
const gpuDial = $("gpuDial");
const gpuText = $("gpuText");
const memoryDial = $("memoryDial");
const memoryText = $("memoryText");
const micStatusText = $("micStatusText");
const clipboardText = $("clipboardText");

let ws = null;
let currentAssistantBubble = null;

// Voice / wake-word state
let wakeWords = ["hey jarvis", "jarvis"];
let wakeEnabled = false; // hands-free "Hey Jarvis" mode
let armed = false; // heard the wake word; next utterance is the command
let speaking = false; // TTS is talking — ignore the mic so it can't hear itself
let speakResponsesEnabled = true;

// Active Chat sessions state
let sessions = [];
let activeSessionId = null;

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
  type_text: "⌨️ typing text",
  press_key: "⌨️ pressing key",
  run_system_command: "⚙️ running system command",
};

// ── Markdown and Code Highlights ──────────────────────────────────────────────
function parseMarkdown(text) {
  try {
    if (window.marked && typeof window.marked.parse === "function") {
      return window.marked.parse(text);
    }
  } catch (e) {
    console.error("Markdown parsing failed, falling back to simple text.", e);
  }
  // Simple regex fallbacks for basic markdown offline
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br>")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/`(.*?)`/g, "<code>$1</code>");
}

function formatCodeBlocks(container) {
  const preElements = container.querySelectorAll("pre");
  preElements.forEach((pre) => {
    if (pre.parentElement.classList.contains("code-block-wrapper")) return;
    
    const wrapper = document.createElement("div");
    wrapper.className = "code-block-wrapper";
    
    const code = pre.querySelector("code");
    let lang = "code";
    if (code) {
      const classes = Array.from(code.classList);
      const langClass = classes.find(c => c.startsWith("language-"));
      if (langClass) {
        lang = langClass.replace("language-", "");
      }
    }
    
    const header = document.createElement("div");
    header.className = "code-header";
    header.innerHTML = `
      <span>${lang.toUpperCase()}</span>
      <button class="copy-code-btn"><i class="fa-regular fa-copy"></i> Copy</button>
    `;
    
    const copyBtn = header.querySelector(".copy-code-btn");
    copyBtn.addEventListener("click", () => {
      if (code) {
        navigator.clipboard.writeText(code.textContent);
        copyBtn.innerHTML = `<i class="fa-solid fa-check"></i> Copied!`;
        setTimeout(() => {
          copyBtn.innerHTML = `<i class="fa-regular fa-copy"></i> Copy`;
        }, 2000);
      }
    });
    
    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(header);
    wrapper.appendChild(pre);
  });
  
  if (window.Prism) {
    window.Prism.highlightAllUnder(container);
  }
}

// ── Chat rendering ────────────────────────────────────────────────────────────
function createBubble(role, text) {
  const div = document.createElement("div");
  div.className = `bubble ${role}`;
  
  const avatar = document.createElement("div");
  avatar.className = "bubble-avatar";
  avatar.innerHTML = role === "user" ? '<i data-lucide="user"></i>' : '<span>⚡</span>';
  
  const content = document.createElement("div");
  content.className = "bubble-content";
  
  const header = document.createElement("div");
  header.className = "bubble-header";
  header.innerHTML = `
    <span>${role === "user" ? "Tony Stark" : "JARVIS"}</span>
    <span class="muted" style="font-size: 9px; font-weight: normal;">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
  `;
  
  const body = document.createElement("div");
  body.className = "bubble-body";
  body.innerHTML = parseMarkdown(text);
  
  content.append(header, body);
  div.append(avatar, content);
  messages.appendChild(div);
  
  // Custom format actions
  formatCodeBlocks(body);
  window.lucide.createIcons();
  
  messages.scrollTop = messages.scrollHeight;
  return body;
}

function addBubble(role, text) {
  // Update state in active session
  const activeSession = sessions.find(s => s.id === activeSessionId);
  if (activeSession) {
    activeSession.messages.push({ role, text });
    saveSessions();
    renderSessionList();
  }
  
  // Hide welcome screen if showing
  if (role === "user") {
    welcomeScreen.classList.add("hidden");
    chatPane.classList.remove("hidden");
  }
  
  return createBubble(role, text);
}

function setActivity(text) {
  if (!text) {
    activity.classList.add("hidden");
    activity.innerHTML = "";
  } else {
    activity.classList.remove("hidden");
    activity.innerHTML = `
      <div class="ai-logo-core mx-0" style="width: 24px; height: 24px; font-size: 11px; line-height: 24px;"><span>⚡</span></div>
      <span>${text}</span>
    `;
  }
}

function speak(text) {
  if (!speakResponsesEnabled || !("speechSynthesis" in window)) return;
  const utter = new SpeechSynthesisUtterance(text);
  speaking = true;
  recognizerStop(); // pause listening so the mic doesn't pick up Jarvis
  
  utter.onstart = () => {
    showVoiceOverlay("Speaking...", "speaking");
  };
  
  utter.onend = () => {
    speaking = false;
    hideVoiceOverlay();
    if (wakeEnabled) recognizerStart(); // resume hands-free listening
  };
  
  window.speechSynthesis.cancel();
  
  // Select browser voice if configured
  if (voiceSelect.value) {
    const selectedVoice = window.speechSynthesis.getVoices().find(v => v.name === voiceSelect.value);
    if (selectedVoice) utter.voice = selectedVoice;
  }
  
  window.speechSynthesis.speak(utter);
}

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
    // result is folded into final answer
  } else if (event.type === "final") {
    setActivity("");
    if (currentAssistantBubble) {
      currentAssistantBubble.innerHTML = parseMarkdown(event.text);
      formatCodeBlocks(currentAssistantBubble);
      
      // Update session storage content
      const activeSession = sessions.find(s => s.id === activeSessionId);
      if (activeSession && activeSession.messages.length > 0) {
        // Last message is the assistant placeholder "..."
        activeSession.messages[activeSession.messages.length - 1].text = event.text;
        
        // Auto rename if it was just "New Chat" and contains first exchange
        if (activeSession.title === "New Chat" && activeSession.messages.length >= 2) {
          activeSession.title = activeSession.messages[0].text.substring(0, 24) + "...";
        }
        saveSessions();
        renderSessionList();
      }
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
    // HTTP fallback
    fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    })
      .then((r) => r.json())
      .then((d) => handleEvent({ type: "final", text: d.reply }))
      .catch((e) => {
        setActivity("");
        if (currentAssistantBubble) {
          currentAssistantBubble.textContent = "Error communicating with server.";
        }
      });
  }
}

function setStatus(on, text) {
  statusDot.classList.toggle("on", on);
  statusText.textContent = text;
}

// ── Voice input + wake word (Web Speech API) ──────────────────────────────────
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;

if (SR) {
  recognition = new SR();
  recognition.lang = "en-US";
  recognition.continuous = true;
  recognition.interimResults = false;
  recognition.onresult = onSpeech;
  recognition.onerror = (e) => {
    if (e.error === "not-allowed") {
      setWake(false);
      setStatus(false, "Mic blocked — allow microphone access");
      micStatusText.textContent = "Blocked";
      micStatusText.className = "val inactive";
    }
  };
  recognition.onend = () => {
    if (wakeEnabled && !speaking) recognizerStart();
  };
} else {
  micBtn.title = "Voice input not supported in this browser";
  wakeBtn.disabled = true;
  micStatusText.textContent = "Not Supported";
  micStatusText.className = "val inactive";
}

function recognizerStart() {
  try {
    recognition.start();
    micStatusText.textContent = "Listening";
    micStatusText.className = "val active";
  } catch (e) {
    /* already started */
  }
}
function recognizerStop() {
  try {
    recognition.stop();
    micStatusText.textContent = "Inactive";
    micStatusText.className = "val inactive";
    hideVoiceOverlay();
  } catch (e) {
    /* already stopped */
  }
}

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
  if (speaking) return; 
  const text = e.results[e.results.length - 1][0].transcript.trim().toLowerCase();
  if (!text) return;

  const afterWake = stripWake(text);
  if (afterWake !== null) {
    if (afterWake) {
      sendMessage(afterWake);
    } else {
      armed = true;
      setStatus(true, "🎙️ Listening — say your command");
      showVoiceOverlay("Listening...", "listening");
    }
    return;
  }

  if (armed) {
    armed = false;
    sendMessage(text);
    hideVoiceOverlay();
    if (!wakeEnabled) recognizerStop();
  }
}

function setWake(on) {
  wakeEnabled = on;
  armed = false;
  settingWakeToggle.checked = on;
  
  if (on) {
    wakeBtn.innerHTML = '<i data-lucide="mic"></i> <span>Hey Jarvis: ON</span>';
    wakeBtn.classList.add("active");
    recognizerStart();
    setStatus(true, 'Hands-free — say "Hey Jarvis"');
  } else {
    wakeBtn.innerHTML = '<i data-lucide="mic"></i> <span>Hey Jarvis: OFF</span>';
    wakeBtn.classList.remove("active");
    recognizerStop();
    setStatus(true, "Ready");
  }
  window.lucide.createIcons();
}

wakeBtn.addEventListener("click", () => setWake(!wakeEnabled));
micBtn.addEventListener("click", () => {
  if (!recognition) return;
  armed = true;
  setStatus(true, "🎙️ Listening…");
  showVoiceOverlay("Listening...", "listening");
  recognizerStart();
});

function showVoiceOverlay(statusMsg, state) {
  voiceOverlayStatus.textContent = statusMsg;
  voiceOverlay.classList.remove("hidden");
  const bars = document.querySelectorAll(".wave-bar");
  if (state === "speaking") {
    bars.forEach(b => b.style.animationPlayState = "running");
  } else {
    // quieter pulse when listening
    bars.forEach((b, idx) => {
      b.style.animationPlayState = "running";
      b.style.animationDuration = (0.6 + (idx * 0.1)) + "s";
    });
  }
}

function hideVoiceOverlay() {
  voiceOverlay.classList.add("hidden");
}

closeVoiceOverlayBtn.addEventListener("click", () => {
  armed = false;
  recognizerStop();
  hideVoiceOverlay();
  if (wakeEnabled) recognizerStart();
});

// ── Files ─────────────────────────────────────────────────────────────────────
async function loadFiles() {
  const res = await fetch("/files").then((r) => r.json());
  fileList.innerHTML = "";
  
  let totalBytes = 0;
  for (const f of res.files) {
    totalBytes += (f.size || 0);
    const li = document.createElement("li");
    
    const icon = document.createElement("i");
    icon.setAttribute("data-lucide", "file");
    
    const a = document.createElement("a");
    a.href = `/files/${encodeURIComponent(f.name)}`;
    a.textContent = f.name;
    a.className = "name";
    a.target = "_blank";
    
    const ask = document.createElement("button");
    ask.title = "Ask Jarvis about this file";
    ask.innerHTML = '<i data-lucide="help-circle"></i>';
    ask.onclick = () => sendMessage(`Summarize the file ${f.name}`);
    
    li.append(icon, a, ask);
    fileList.appendChild(li);
  }
  
  // Update storage usage layout dynamically
  const sizeMB = (totalBytes / (1024 * 1024)).toFixed(1);
  const percent = Math.min(((totalBytes / (10 * 1024 * 1024 * 1024)) * 100), 100).toFixed(1);
  $("storageText").textContent = `${sizeMB} MB / 10 GB`;
  $("storageProgress").style.width = `${percent}%`;
  
  window.lucide.createIcons();
}

async function uploadFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  setActivity("Uploading file...");
  try {
    await fetch("/files/upload", { method: "POST", body: fd });
    setActivity("");
    loadFiles();
  } catch(e) {
    setActivity("Upload failed.");
    setTimeout(() => setActivity(""), 2000);
  }
}

dropZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) uploadFile(fileInput.files[0]);
});
$("clipBtn").addEventListener("click", () => fileInput.click());

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

// ── Memory / Facts ────────────────────────────────────────────────────────────
async function loadFacts() {
  const res = await fetch("/memory/facts").then((r) => r.json());
  factList.innerHTML = "";
  $("factCountBadge").textContent = res.facts.length;
  $("memoryBadgeText").textContent = `${res.facts.length} fact${res.facts.length === 1 ? '' : 's'}`;
  
  for (const f of res.facts) {
    const li = document.createElement("li");
    const kv = document.createElement("div");
    kv.className = "kv";
    kv.innerHTML = `<span class="k">${f.key}</span><span class="v">${f.value}</span>`;
    
    const del = document.createElement("button");
    del.innerHTML = '<i data-lucide="trash-2"></i>';
    del.title = "Delete Fact";
    del.onclick = async () => {
      await fetch(`/memory/facts/${encodeURIComponent(f.key)}`, { method: "DELETE" });
      loadFacts();
    };
    li.append(kv, del);
    factList.appendChild(li);
  }
  window.lucide.createIcons();
}

clearHistoryBtn.addEventListener("click", async () => {
  const activeSession = sessions.find(s => s.id === activeSessionId);
  if (activeSession) {
    activeSession.messages = [];
    saveSessions();
  }
  await fetch("/memory/clear", { method: "POST" });
  messages.innerHTML = "";
  welcomeScreen.classList.remove("hidden");
  chatPane.classList.add("hidden");
});

// ── Multiple Chat Sessions State Management ──────────────────────────────────
function initSessions() {
  const stored = localStorage.getItem("jarvis_sessions");
  if (stored) {
    try {
      sessions = JSON.parse(stored);
    } catch(e) {
      sessions = [];
    }
  }
  
  if (!sessions || sessions.length === 0) {
    createNewSession();
  } else {
    activeSessionId = sessions[0].id;
    loadSession(activeSessionId);
  }
}

function createNewSession() {
  const newSession = {
    id: Date.now().toString(),
    title: "New Chat",
    messages: [],
    pinned: false
  };
  sessions.unshift(newSession);
  saveSessions();
  activeSessionId = newSession.id;
  loadSession(activeSessionId);
  renderSessionList();
  
  // Wipe server-side short-term memory as well so conversations don't cross
  fetch("/memory/clear", { method: "POST" });
}

function saveSessions() {
  localStorage.setItem("jarvis_sessions", JSON.stringify(sessions));
}

function loadSession(id) {
  activeSessionId = id;
  const activeSession = sessions.find(s => s.id === id);
  if (!activeSession) return;
  
  messages.innerHTML = "";
  
  if (activeSession.messages.length === 0) {
    welcomeScreen.classList.remove("hidden");
    chatPane.classList.add("hidden");
  } else {
    welcomeScreen.classList.add("hidden");
    chatPane.classList.remove("hidden");
    
    // Render existing session messages
    activeSession.messages.forEach(m => {
      createBubble(m.role, m.text);
    });
  }
  
  renderSessionList();
}

function deleteSession(id, e) {
  if (e) e.stopPropagation();
  sessions = sessions.filter(s => s.id !== id);
  saveSessions();
  
  if (sessions.length === 0) {
    createNewSession();
  } else if (activeSessionId === id) {
    activeSessionId = sessions[0].id;
    loadSession(activeSessionId);
  }
  renderSessionList();
}

function togglePinSession(id, e) {
  if (e) e.stopPropagation();
  const session = sessions.find(s => s.id === id);
  if (session) {
    session.pinned = !session.pinned;
    // Sort pinned to top
    sessions.sort((a,b) => {
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      return 0;
    });
    saveSessions();
    renderSessionList();
  }
}

function renderSessionList() {
  historyList.innerHTML = "";
  
  // Filter sessions if searching
  const query = chatSearch.value.trim().toLowerCase();
  const filtered = sessions.filter(s => {
    if (!query) return true;
    return s.title.toLowerCase().includes(query) || 
           s.messages.some(m => m.text.toLowerCase().includes(query));
  });
  
  filtered.forEach(s => {
    const li = document.createElement("li");
    li.className = `history-item ${s.id === activeSessionId ? 'active' : ''}`;
    li.onclick = () => loadSession(s.id);
    
    const titleSpan = document.createElement("span");
    titleSpan.className = "title-text";
    titleSpan.textContent = s.title;
    
    const actions = document.createElement("div");
    actions.className = "item-actions";
    
    const pinBtn = document.createElement("button");
    pinBtn.innerHTML = s.pinned ? '<i data-lucide="pin-off" style="width: 12px;"></i>' : '<i data-lucide="pin" style="width: 12px;"></i>';
    pinBtn.title = s.pinned ? "Unpin Chat" : "Pin Chat";
    pinBtn.onclick = (e) => togglePinSession(s.id, e);
    
    const delBtn = document.createElement("button");
    delBtn.innerHTML = '<i data-lucide="trash" style="width: 12px;"></i>';
    delBtn.title = "Delete Chat";
    delBtn.onclick = (e) => deleteSession(s.id, e);
    
    actions.append(pinBtn, delBtn);
    li.append(titleSpan, actions);
    historyList.appendChild(li);
  });
  window.lucide.createIcons();
}

newChatBtn.addEventListener("click", createNewSession);
chatSearch.addEventListener("input", renderSessionList);

// ── Sidebar Controls ──────────────────────────────────────────────────────────
toggleLeftSidebar.addEventListener("click", () => {
  leftSidebar.classList.add("collapsed");
  expandLeftSidebar.classList.remove("hidden");
});
expandLeftSidebar.addEventListener("click", () => {
  leftSidebar.classList.remove("collapsed");
  expandLeftSidebar.classList.add("hidden");
});

toggleRightSidebar.addEventListener("click", () => {
  rightSidebar.classList.toggle("collapsed");
});
toggleRightSidebarClose.addEventListener("click", () => {
  rightSidebar.classList.add("collapsed");
});

// ── Welcome Screen Cards trigger ──────────────────────────────────────────────
document.querySelectorAll(".suggest-card").forEach(card => {
  card.addEventListener("click", () => {
    const prompt = card.getAttribute("data-prompt");
    textInput.value = prompt;
    sendMessage(prompt);
    textInput.value = "";
    textInput.rows = 1;
  });
});

// Mouse glow effects on suggestion cards
document.querySelectorAll(".suggest-card").forEach(card => {
  card.addEventListener("mousemove", (e) => {
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    card.style.setProperty("--mouse-x", `${x}px`);
    card.style.setProperty("--mouse-y", `${y}px`);
  });
});

// ── Settings Modal Tabs & Pane Toggle ─────────────────────────────────────────
openSettingsBtn.addEventListener("click", () => {
  settingsModal.classList.remove("hidden");
  loadFacts();
});
closeSettingsModalBtn.addEventListener("click", () => {
  settingsModal.classList.add("hidden");
});

settingsTabs.forEach(tab => {
  tab.addEventListener("click", () => {
    // Update active tab styling
    settingsTabs.forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    
    // Switch active settings pane
    const targetTab = tab.getAttribute("data-tab");
    settingsTabTitle.textContent = tab.textContent.trim();
    
    settingsPanes.forEach(pane => {
      pane.classList.remove("active");
      if (pane.id === `pane-${targetTab}`) {
        pane.classList.add("active");
      }
    });
  });
});

// ── Settings Subcomponents Controllers ────────────────────────────────────────
// Voices Loader
function loadVoiceList() {
  if (!("speechSynthesis" in window)) return;
  const list = window.speechSynthesis.getVoices();
  voiceSelect.innerHTML = "";
  
  list.forEach(v => {
    const opt = document.createElement("option");
    opt.value = v.name;
    opt.textContent = `${v.name} (${v.lang})`;
    if (v.default) opt.selected = true;
    voiceSelect.appendChild(opt);
  });
}
if ("speechSynthesis" in window) {
  window.speechSynthesis.onvoiceschanged = loadVoiceList;
  loadVoiceList();
}

settingSpeakToggle.addEventListener("change", () => {
  speakResponsesEnabled = settingSpeakToggle.checked;
});

settingWakeToggle.addEventListener("change", () => {
  setWake(settingWakeToggle.checked);
});

// Model selector configuration mapping
settingsProvider.addEventListener("change", () => {
  if (settingsProvider.value === "openai_compatible") {
    cloudModelGroup.style.display = "block";
  } else {
    cloudModelGroup.style.display = "none";
  }
});

// Sync main screen inputs to settings panel values
dangerousToolsSwitch.addEventListener("change", () => {
  const isEnabled = dangerousToolsSwitch.checked;
  dangerBadge.classList.toggle("hidden", !isEnabled);
  $("sysSafety").textContent = isEnabled ? "Dangerous Tools Allowed (Unrestricted)" : "Sandboxed (Dangerous Tools Off)";
  $("dangerToolStatusPlugin").className = `plugin-status ${isEnabled ? 'active' : 'inactive'}`;
  $("dangerToolStatusPlugin").textContent = isEnabled ? "Active" : "Inactive";
});

async function updateConfig(model, temperature) {
  const payload = {};
  if (model) payload.model = model;
  if (temperature !== undefined) payload.temperature = parseFloat(temperature);
  
  try {
    const res = await fetch("/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }).then(r => r.json());
    
    if (res.status === "success") {
      modelInfo.textContent = `ollama · ${res.model}`;
      console.log("Config updated:", res);
    }
  } catch(e) {
    console.error("Failed to update config:", e);
  }
}

modelSelector.addEventListener("change", () => {
  updateConfig(modelSelector.value, undefined);
});

tempSlider.addEventListener("input", () => {
  tempValue.textContent = tempSlider.value;
});

tempSlider.addEventListener("change", () => {
  updateConfig(undefined, tempSlider.value);
});

// Theme switcher logic
document.querySelectorAll(".theme-option").forEach(opt => {
  opt.addEventListener("click", () => {
    document.querySelectorAll(".theme-option").forEach(o => o.classList.remove("active"));
    opt.classList.add("active");
    const theme = opt.getAttribute("data-theme-val");
    
    if (theme === "system") {
      const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
    } else {
      document.documentElement.setAttribute("data-theme", theme);
    }
  });
});

// Keyboard Startup Config Trigger
$("toggleStartupBtn").addEventListener("click", () => {
  alert("Startup options are managed using the local installation batch scripts: 'install_startup.bat' and 'uninstall_startup.bat' inside your workspace directory.");
});

// ── Command Palette Controller (Ctrl + K) ─────────────────────────────────────
const COMMANDS = [
  { name: "Create New Chat", keys: "Ctrl + N", action: () => createNewSession(), category: "Navigation" },
  { name: "Clear Current Chat Logs", keys: "Ctrl + Shift + X", action: () => $("clearHistoryBtn").click(), category: "History" },
  { name: "Open Settings", keys: "Ctrl + ,", action: () => openSettingsBtn.click(), category: "System" },
  { name: "Enable Hey Jarvis Wake-Word", keys: "", action: () => setWake(true), category: "Audio" },
  { name: "Disable Hey Jarvis Wake-Word", keys: "", action: () => setWake(false), category: "Audio" },
  { name: "Toggle Theme: Dark Mode", keys: "", action: () => document.querySelector('[data-theme-val="dark"]').click(), category: "Appearance" },
  { name: "Toggle Theme: Light Mode", keys: "", action: () => document.querySelector('[data-theme-val="light"]').click(), category: "Appearance" },
  { name: "Toggle Right Context Panel", keys: "Ctrl + B", action: () => toggleRightSidebar.click(), category: "Layout" },
  { name: "Run Time Tool (get_time)", keys: "", action: () => sendMessage("What is the time?"), category: "Tools" },
  { name: "Search Google (web_search)", keys: "", action: () => {
    commandPalette.classList.add("hidden");
    textInput.value = "Search the web for ";
    textInput.focus();
  }, category: "Tools" },
  { name: "List Workspace Files (list_files)", keys: "", action: () => sendMessage("List files"), category: "Tools" },
];

function toggleCommandPalette(show) {
  if (show) {
    commandPalette.classList.remove("hidden");
    paletteSearch.value = "";
    paletteSearch.focus();
    renderPaletteResults("");
  } else {
    commandPalette.classList.add("hidden");
  }
}

function renderPaletteResults(query) {
  paletteResults.innerHTML = "";
  const filtered = COMMANDS.filter(cmd => cmd.name.toLowerCase().includes(query.toLowerCase()));
  
  if (filtered.length === 0) {
    paletteResults.innerHTML = '<li class="palette-item muted">No results found</li>';
    return;
  }
  
  filtered.forEach((cmd, idx) => {
    const li = document.createElement("li");
    li.className = `palette-item ${idx === 0 ? 'selected' : ''}`;
    li.innerHTML = `
      <i data-lucide="terminal"></i>
      <span>${cmd.name}</span>
      ${cmd.keys ? `<span class="kbd">${cmd.keys}</span>` : ''}
      <span class="category">${cmd.category}</span>
    `;
    li.onclick = () => {
      cmd.action();
      toggleCommandPalette(false);
    };
    paletteResults.appendChild(li);
  });
  window.lucide.createIcons();
}

paletteSearch.addEventListener("input", (e) => {
  renderPaletteResults(e.target.value);
});

// Arrow navigation in palette
paletteSearch.addEventListener("keydown", (e) => {
  const items = paletteResults.querySelectorAll(".palette-item:not(.muted)");
  if (items.length === 0) return;
  
  let selectedIdx = Array.from(items).findIndex(item => item.classList.contains("selected"));
  
  if (e.key === "ArrowDown") {
    e.preventDefault();
    if (selectedIdx !== -1) items[selectedIdx].classList.remove("selected");
    selectedIdx = (selectedIdx + 1) % items.length;
    items[selectedIdx].classList.add("selected");
    items[selectedIdx].scrollIntoView({ block: "nearest" });
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    if (selectedIdx !== -1) items[selectedIdx].classList.remove("selected");
    selectedIdx = (selectedIdx - 1 + items.length) % items.length;
    items[selectedIdx].classList.add("selected");
    items[selectedIdx].scrollIntoView({ block: "nearest" });
  } else if (e.key === "Enter") {
    e.preventDefault();
    if (selectedIdx !== -1) {
      items[selectedIdx].click();
    }
  } else if (e.key === "Escape") {
    toggleCommandPalette(false);
  }
});

// Global Shortcuts Listeners
window.addEventListener("keydown", (e) => {
  // Ctrl + K -> Command Palette
  if (e.ctrlKey && e.key.toLowerCase() === "k") {
    e.preventDefault();
    toggleCommandPalette(commandPalette.classList.contains("hidden"));
  }
  // Ctrl + , -> Settings
  if (e.ctrlKey && e.key === ",") {
    e.preventDefault();
    settingsModal.classList.toggle("hidden");
  }
  // Ctrl + N -> New Session
  if (e.ctrlKey && e.key.toLowerCase() === "n") {
    e.preventDefault();
    createNewSession();
  }
  // Ctrl + B -> Toggle Right Sidebar
  if (e.ctrlKey && e.key.toLowerCase() === "b") {
    e.preventDefault();
    toggleRightSidebar.click();
  }
  // Esc -> Hide overlays
  if (e.key === "Escape") {
    toggleCommandPalette(false);
    settingsModal.classList.add("hidden");
    hideVoiceOverlay();
  }
});

// Hide palettes when clicking outside cards
[settingsModal, commandPalette].forEach(overlay => {
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) {
      overlay.classList.add("hidden");
    }
  });
});

// ── System Metrics Live Loop ───────────────────────────────────────────
function updateSystemMetrics() {
  // Fluctuating values for real dynamic look
  const cpu = Math.floor(Math.random() * 16) + 6; // 6% - 22%
  const ram = Math.floor(Math.random() * 8) + 42;  // 42% - 50%
  const gpu = Math.floor(Math.random() * 6) + 2;   // 2% - 8%
  
  // Radial calculations
  cpuDial.style.setProperty("--value", cpu);
  cpuText.textContent = `${cpu}%`;
  
  ramDial.style.setProperty("--value", ram);
  ramText.textContent = `${ram}%`;
  
  gpuDial.style.setProperty("--value", gpu);
  gpuText.textContent = `${gpu}%`;
  
  // Memory fluctuations (mock size dial)
  const memUsage = Math.floor(Math.random() * 50) + 230; // 230MB - 280MB
  const memPct = Math.floor((memUsage / 1024) * 100);
  memoryDial.style.setProperty("--value", memPct);
  memoryText.textContent = `${memUsage}MB`;
  
  // Update Clipboard preview helper
  navigator.clipboard.readText()
    .then(text => {
      if (text) {
        clipboardText.textContent = text.substring(0, 70) + (text.length > 70 ? '...' : '');
        clipboardText.classList.remove("muted");
      }
    })
    .catch(() => {
      // Permission blocked or browser doesn't support background query
    });
}
setInterval(updateSystemMetrics, 3000);
updateSystemMetrics();

// Set Calendar Widgets values
function initCalendar() {
  const d = new Date();
  const months = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"];
  const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  
  $("calMonth").textContent = months[d.getMonth()];
  $("calYear").textContent = d.getFullYear();
  $("calDayName").textContent = days[d.getDay()];
  $("calDayNum").textContent = d.getDate();
}
initCalendar();

// Clipboard click to copy to input bar
$("pasteClipboardBtn").addEventListener("click", async () => {
  try {
    const text = await navigator.clipboard.readText();
    if (text) {
      textInput.value += text;
      textInput.focus();
    }
  } catch(e) {}
});

// ── Auto-growing text area inside Input Bar ──────────────────────────────────
textInput.addEventListener("input", () => {
  textInput.style.height = "auto";
  textInput.style.height = (textInput.scrollHeight - 6) + "px";
});

// ── Wire up & boot ────────────────────────────────────────────────────────────
sendBtn.addEventListener("click", () => {
  sendMessage(textInput.value);
  textInput.value = "";
  textInput.style.height = "auto";
});
textInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage(textInput.value);
    textInput.value = "";
    textInput.style.height = "auto";
  }
});

async function loadModels() {
  try {
    const res = await fetch("/models").then(r => r.json());
    if (res.models && res.models.length > 0) {
      modelSelector.innerHTML = "";
      res.models.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        if (m === res.active) opt.selected = true;
        modelSelector.appendChild(opt);
      });
      modelInfo.textContent = `${res.provider} · ${res.active}`;
    }
  } catch (e) {
    console.error("Failed to load models list:", e);
  }
}

async function boot() {
  try {
    const h = await fetch("/health").then((r) => r.json());
    await loadModels();
    
    // Set settings info
    $("sysHost").textContent = `${location.host}`;
    $("sysWorkspace").textContent = `./workspace`;
    
    // Check dangerous tools
    if (h.dangerous_tools_enabled) {
      dangerBadge.classList.remove("hidden");
      dangerousToolsSwitch.checked = true;
      $("sysSafety").textContent = "Dangerous Tools Allowed (Unrestricted)";
      $("dangerToolStatusPlugin").className = "plugin-status active";
      $("dangerToolStatusPlugin").textContent = "Active";
    }
    
    if (Array.isArray(h.wake_words) && h.wake_words.length) {
      wakeWords = h.wake_words.map((w) => w.toLowerCase());
    }
  } catch (e) {
    console.error("Health query failed", e);
  }
  
  // Fetch messages from backend if any, to seed sessions if local storage is blank
  try {
    const past = await fetch("/messages").then((r) => r.json());
    if (past.messages && past.messages.length > 0 && sessions.length <= 1 && sessions[0].messages.length === 0) {
      // populate active session with SQLite messages
      const activeSession = sessions[0];
      activeSession.title = past.messages[0].content.substring(0, 24) + "...";
      past.messages.forEach(m => {
        // SQLite uses "role" and "content" fields
        activeSession.messages.push({ role: m.role, text: m.content });
      });
      saveSessions();
    }
  } catch(e) {
    console.error("Failed to load historical messages from DB", e);
  }
  
  initSessions();
  connectWS();
  loadFiles();
  loadFacts();
}
boot();
