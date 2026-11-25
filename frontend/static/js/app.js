const STORAGE_KEY = "oracle_chat_settings";

const DEFAULT_SETTINGS = {
    provider: "openrouter",
    openrouterApiKey: "",
    openrouterModel: "google/gemma-4-31b-it:free",
    ollamaBaseUrl: "http://localhost:11434",
    ollamaModel: "",
};

// DOM Elements - Chat
const chatView = document.getElementById("chat-view");
const settingsView = document.getElementById("settings-view");
const chatHistory = document.getElementById("chat-history");
const emptyState = document.getElementById("empty-state");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const providerBadge = document.getElementById("provider-badge");

// DOM Elements - Settings
const settingsBtn = document.getElementById("settings-btn");
const backToChatBtn = document.getElementById("back-to-chat-btn");
const settingsForm = document.getElementById("settings-form");
const providerRadios = document.querySelectorAll('input[name="provider"]');
const openrouterSection = document.getElementById("openrouter-section");
const ollamaSection = document.getElementById("ollama-section");
const openrouterApiKeyInput = document.getElementById("openrouter-api-key");
const toggleKeyBtn = document.getElementById("toggle-key-btn");
const openrouterModelInput = document.getElementById("openrouter-model");
const ollamaBaseUrlInput = document.getElementById("ollama-base-url");
const discoverOllamaBtn = document.getElementById("discover-ollama-btn");
const ollamaDiscoveryStatus = document.getElementById("ollama-discovery-status");
const ollamaModelSelect = document.getElementById("ollama-model-select");
const ollamaCustomModelInput = document.getElementById("ollama-custom-model");
const resetSettingsBtn = document.getElementById("reset-settings-btn");
const settingsSaveFeedback = document.getElementById("settings-save-feedback");
const openLogsFromSettingsBtn = document.getElementById("open-logs-from-settings-btn");

// DOM Elements - Log Window
const logsToggleBtn = document.getElementById("logs-toggle-btn");
const logErrorBadge = document.getElementById("log-error-badge");
const logDrawer = document.getElementById("log-drawer");
const logOutput = document.getElementById("log-output");
const copyLogsBtn = document.getElementById("copy-logs-btn");
const clearLogsBtn = document.getElementById("clear-logs-btn");
const closeLogsBtn = document.getElementById("close-logs-btn");
const logFilterButtons = document.querySelectorAll(".filter-btn");

let currentSettings = loadSettings();
const logEntries = [];
let activeLogFilter = "all";

// ---------------------------
// Event & Error Logging
// ---------------------------
function formatTimestamp(date = new Date()) {
    return date.toTimeString().split(" ")[0];
}

function addLog(level, source, message, details = null) {
    const entry = {
        timestamp: formatTimestamp(),
        level, // "INFO" | "WARN" | "ERROR"
        source,
        message,
        details: details ? (typeof details === "string" ? details : JSON.stringify(details)) : "",
    };
    logEntries.push(entry);
    renderLogs();
    updateErrorBadge();
}

function updateErrorBadge() {
    const errorCount = logEntries.filter((entry) => entry.level === "ERROR").length;
    if (errorCount > 0) {
        logErrorBadge.textContent = String(errorCount);
        logErrorBadge.classList.remove("hidden");
    } else {
        logErrorBadge.classList.add("hidden");
    }
}

function formatLogLine(entry) {
    const suffix = entry.details ? ` | ${entry.details}` : "";
    return `[${entry.timestamp}] [${entry.level}] [${entry.source}] ${entry.message}${suffix}`;
}

function renderLogs() {
    const filtered = logEntries.filter((entry) => {
        if (activeLogFilter === "error") {
            return entry.level === "ERROR";
        }
        if (activeLogFilter === "event") {
            return entry.level !== "ERROR";
        }
        return true;
    });

    logOutput.innerHTML = "";
    if (filtered.length === 0) {
        const empty = document.createElement("div");
        empty.className = "log-entry level-info";
        empty.textContent = "No matching log entries yet.";
        logOutput.appendChild(empty);
        return;
    }

    for (const entry of filtered) {
        const line = document.createElement("div");
        line.className = `log-entry level-${entry.level.toLowerCase()}`;
        line.textContent = formatLogLine(entry);
        logOutput.appendChild(line);
    }

    logOutput.scrollTop = logOutput.scrollHeight;
}

function toggleLogDrawer(forceOpen = null) {
    const shouldOpen = forceOpen !== null ? forceOpen : logDrawer.classList.contains("hidden");
    logDrawer.classList.toggle("hidden", !shouldOpen);
    if (shouldOpen) {
        renderLogs();
    }
}

async function copyLogsToClipboard() {
    const text = logEntries.map(formatLogLine).join("\n") || "No log entries.";
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
        } else {
            const temp = document.createElement("textarea");
            temp.value = text;
            document.body.appendChild(temp);
            temp.select();
            document.execCommand("copy");
            temp.remove();
        }
        const original = copyLogsBtn.textContent;
        copyLogsBtn.textContent = "Copied!";
        addLog("INFO", "LOGS", `Copied ${logEntries.length} log entries to clipboard.`);
        setTimeout(() => {
            copyLogsBtn.textContent = original;
        }, 1500);
    } catch (err) {
        addLog("ERROR", "LOGS", "Failed to copy logs to clipboard.", err.message);
    }
}

window.addEventListener("error", (event) => {
    addLog("ERROR", "WINDOW", event.message || "Uncaught JS error", {
        file: event.filename,
        line: event.lineno,
    });
});

window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason instanceof Error ? event.reason.message : String(event.reason);
    addLog("ERROR", "PROMISE", "Unhandled promise rejection", reason);
});

// ---------------------------
// Settings Management
// ---------------------------
function loadSettings() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) {
            return { ...DEFAULT_SETTINGS };
        }
        return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
    } catch (err) {
        return { ...DEFAULT_SETTINGS };
    }
}

function saveSettingsToStorage(settings) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

function getActiveModelName(settings) {
    if (settings.provider === "ollama") {
        return settings.ollamaModel || "not selected";
    }
    return settings.openrouterModel || DEFAULT_SETTINGS.openrouterModel;
}

function updateHeaderBadge() {
    const providerLabel = currentSettings.provider === "ollama" ? "Ollama" : "OpenRouter";
    const modelName = getActiveModelName(currentSettings);
    providerBadge.textContent = `${providerLabel} · ${modelName}`;
}

function showStatusBanner(element, message, type) {
    element.textContent = message;
    element.className = `status-banner ${type}`;
    element.classList.remove("hidden");
}

function toggleProviderSections(provider) {
    const isOllama = provider === "ollama";
    openrouterSection.classList.toggle("hidden", isOllama);
    ollamaSection.classList.toggle("hidden", !isOllama);
}

function populateSettingsForm(settings) {
    providerRadios.forEach((radio) => {
        radio.checked = radio.value === settings.provider;
    });
    toggleProviderSections(settings.provider);

    openrouterApiKeyInput.value = settings.openrouterApiKey;
    openrouterModelInput.value = settings.openrouterModel;
    ollamaBaseUrlInput.value = settings.ollamaBaseUrl;
    ollamaCustomModelInput.value = settings.ollamaModel;

    if (settings.ollamaModel) {
        const exists = Array.from(ollamaModelSelect.options).some(
            (opt) => opt.value === settings.ollamaModel
        );
        if (!exists) {
            const option = document.createElement("option");
            option.value = settings.ollamaModel;
            option.textContent = `${settings.ollamaModel} (saved)`;
            ollamaModelSelect.appendChild(option);
        }
        ollamaModelSelect.value = settings.ollamaModel;
    } else {
        ollamaModelSelect.value = "";
    }
}

function openSettingsPage() {
    populateSettingsForm(currentSettings);
    settingsSaveFeedback.classList.add("hidden");
    chatView.classList.add("hidden");
    settingsView.classList.remove("hidden");
    addLog("INFO", "UI", "Opened Settings page.");
}

function closeSettingsPage() {
    settingsView.classList.add("hidden");
    chatView.classList.remove("hidden");
    messageInput.focus();
    addLog("INFO", "UI", "Returned to Chat view.");
}

function formatBytes(bytes) {
    if (!bytes || Number.isNaN(bytes)) {
        return "";
    }
    const gb = bytes / (1024 ** 3);
    return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bytes / (1024 ** 2)).toFixed(0)} MB`;
}

async function discoverOllamaModels() {
    const baseUrl = ollamaBaseUrlInput.value.trim() || DEFAULT_SETTINGS.ollamaBaseUrl;
    discoverOllamaBtn.disabled = true;
    discoverOllamaBtn.textContent = "Scanning...";
    showStatusBanner(ollamaDiscoveryStatus, `Contacting Ollama at ${baseUrl}...`, "info");
    addLog("INFO", "OLLAMA", `Starting dynamic model discovery at ${baseUrl}`);

    try {
        const response = await fetch(`/api/ollama/models?base_url=${encodeURIComponent(baseUrl)}`);
        const data = await response.json();

        if (!response.ok) {
            const detail = data.detail || `HTTP ${response.status}`;
            throw new Error(detail);
        }

        ollamaModelSelect.innerHTML = "";
        if (!data.models || data.models.length === 0) {
            const emptyOpt = document.createElement("option");
            emptyOpt.value = "";
            emptyOpt.textContent = "-- No local models found in Ollama --";
            ollamaModelSelect.appendChild(emptyOpt);
            showStatusBanner(
                ollamaDiscoveryStatus,
                `Connected to Ollama at ${data.base_url}, but 0 models were returned. Run "ollama pull gemma3:4b" first.`,
                "info"
            );
            addLog("WARN", "OLLAMA", "Connected to Ollama, 0 models installed.", data.base_url);
            return;
        }

        for (const model of data.models) {
            const opt = document.createElement("option");
            opt.value = model.name;
            const sizeLabel = formatBytes(model.size);
            opt.textContent = sizeLabel ? `${model.name} (${sizeLabel})` : model.name;
            ollamaModelSelect.appendChild(opt);
        }

        const preferred = ollamaCustomModelInput.value.trim() || data.models[0].name;
        const hasPreferred = data.models.some((m) => m.name === preferred);
        ollamaModelSelect.value = hasPreferred ? preferred : data.models[0].name;
        ollamaCustomModelInput.value = ollamaModelSelect.value;

        showStatusBanner(
            ollamaDiscoveryStatus,
            `Discovered ${data.count} Ollama model(s) at ${data.base_url}.`,
            "success"
        );
        addLog(
            "INFO",
            "OLLAMA",
            `Discovered ${data.count} model(s).`,
            data.models.map((m) => m.name).join(", ")
        );
    } catch (err) {
        showStatusBanner(
            ollamaDiscoveryStatus,
            `Discovery failed: ${err.message}. Open Logs for troubleshooting details.`,
            "error"
        );
        addLog("ERROR", "OLLAMA", "Model discovery failed.", err.message);
    } finally {
        discoverOllamaBtn.disabled = false;
        discoverOllamaBtn.textContent = "Discover Models";
    }
}

// ---------------------------
// Chat UI
// ---------------------------
function updateSendButtonState() {
    sendButton.disabled = messageInput.value.trim().length === 0;
}

function autoResizeInput() {
    messageInput.style.height = "auto";
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 160)}px`;
}

function scrollToBottom() {
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function appendMessage(role, text) {
    if (emptyState && emptyState.parentNode) {
        emptyState.remove();
    }

    const row = document.createElement("div");
    row.className = `message-row ${role}`;

    const roleLabel = document.createElement("span");
    roleLabel.className = "message-role";
    roleLabel.textContent = role === "user" ? "You" : "Assistant";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.textContent = text;

    row.appendChild(roleLabel);
    row.appendChild(bubble);
    chatHistory.appendChild(row);
    scrollToBottom();
}

function handleSend(event) {
    event.preventDefault();

    const text = messageInput.value.trim();
    if (!text) {
        return;
    }

    appendMessage("user", text);
    addLog("INFO", "CHAT", "User submitted message in UI preview.", `length=${text.length}`);

    messageInput.value = "";
    autoResizeInput();
    updateSendButtonState();
    messageInput.focus();

    const activeProvider = currentSettings.provider;
    const activeModel = getActiveModelName(currentSettings);
    appendMessage(
        "assistant",
        `UI Preview (${activeProvider} · ${activeModel}) received: "${text}"`
    );
}

// ---------------------------
// Event Listeners
// ---------------------------
messageInput.addEventListener("input", () => {
    autoResizeInput();
    updateSendButtonState();
});

messageInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        if (!sendButton.disabled) {
            chatForm.requestSubmit();
        }
    }
});

chatForm.addEventListener("submit", handleSend);

settingsBtn.addEventListener("click", openSettingsPage);
backToChatBtn.addEventListener("click", closeSettingsPage);

providerRadios.forEach((radio) => {
    radio.addEventListener("change", (event) => {
        toggleProviderSections(event.target.value);
        addLog("INFO", "SETTINGS", `Switched provider selection to ${event.target.value}.`);
    });
});

toggleKeyBtn.addEventListener("click", () => {
    const isHidden = openrouterApiKeyInput.type === "password";
    openrouterApiKeyInput.type = isHidden ? "text" : "password";
    toggleKeyBtn.textContent = isHidden ? "Hide" : "Show";
});

discoverOllamaBtn.addEventListener("click", discoverOllamaModels);

ollamaModelSelect.addEventListener("change", () => {
    if (ollamaModelSelect.value) {
        ollamaCustomModelInput.value = ollamaModelSelect.value;
    }
});

settingsForm.addEventListener("submit", (event) => {
    event.preventDefault();

    const selectedProvider = document.querySelector('input[name="provider"]:checked').value;
    const updated = {
        provider: selectedProvider,
        openrouterApiKey: openrouterApiKeyInput.value.trim(),
        openrouterModel: openrouterModelInput.value.trim() || DEFAULT_SETTINGS.openrouterModel,
        ollamaBaseUrl: ollamaBaseUrlInput.value.trim() || DEFAULT_SETTINGS.ollamaBaseUrl,
        ollamaModel: ollamaCustomModelInput.value.trim() || ollamaModelSelect.value,
    };

    if (selectedProvider === "openrouter" && !updated.openrouterApiKey) {
        addLog("WARN", "SETTINGS", "Saved OpenRouter provider without an API key.");
    }
    if (selectedProvider === "ollama" && !updated.ollamaModel) {
        addLog("WARN", "SETTINGS", "Saved Ollama provider without a selected model.");
    }

    currentSettings = updated;
    saveSettingsToStorage(currentSettings);
    updateHeaderBadge();

    showStatusBanner(
        settingsSaveFeedback,
        `Settings saved (${currentSettings.provider} · ${getActiveModelName(currentSettings)}).`,
        "success"
    );
    addLog("INFO", "SETTINGS", "Settings saved.", {
        provider: currentSettings.provider,
        model: getActiveModelName(currentSettings),
        hasOpenRouterKey: Boolean(currentSettings.openrouterApiKey),
        ollamaBaseUrl: currentSettings.ollamaBaseUrl,
    });
});

resetSettingsBtn.addEventListener("click", () => {
    currentSettings = { ...DEFAULT_SETTINGS };
    saveSettingsToStorage(currentSettings);
    populateSettingsForm(currentSettings);
    updateHeaderBadge();
    showStatusBanner(settingsSaveFeedback, "Settings reset to defaults.", "info");
    addLog("INFO", "SETTINGS", "Settings reset to defaults.");
});

logsToggleBtn.addEventListener("click", () => toggleLogDrawer());
openLogsFromSettingsBtn.addEventListener("click", () => toggleLogDrawer(true));
closeLogsBtn.addEventListener("click", () => toggleLogDrawer(false));
copyLogsBtn.addEventListener("click", copyLogsToClipboard);
clearLogsBtn.addEventListener("click", () => {
    logEntries.length = 0;
    addLog("INFO", "LOGS", "Log buffer cleared.");
});

logFilterButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
        activeLogFilter = btn.dataset.filter;
        logFilterButtons.forEach((item) => item.classList.toggle("active", item === btn));
        renderLogs();
    });
});

// Initialize
updateHeaderBadge();
addLog("INFO", "APP", "ORACLE CHAT UI initialized.", {
    provider: currentSettings.provider,
    model: getActiveModelName(currentSettings),
});
