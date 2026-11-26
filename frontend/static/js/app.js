const STORAGE_KEY = "oracle_chat_settings";
const SESSION_STORAGE_KEY = "oracle_chat_session_id";

const DEFAULT_SETTINGS = {
    provider: "openrouter",
    openrouterApiKey: "",
    openrouterModel: "openrouter/free",
    pinnedOpenRouterModel: "",
    pinnedVisionModel: "",
    ollamaBaseUrl: "",
    ollamaModel: "",
};

const IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"];
const DOC_EXTENSIONS = [".pdf", ".txt"];

// DOM Elements - Sidebar & Sessions
const chatSidebar = document.getElementById("chat-sidebar");
const sidebarToggleBtn = document.getElementById("sidebar-toggle-btn");
const sidebarCloseBtn = document.getElementById("sidebar-close-btn");
const sidebarNewChatBtn = document.getElementById("sidebar-new-chat-btn");
const sessionList = document.getElementById("session-list");

// DOM Elements - Chat
const chatView = document.getElementById("chat-view");
const settingsView = document.getElementById("settings-view");
const chatHistory = document.getElementById("chat-history");
const emptyStateTemplate = document.getElementById("empty-state").cloneNode(true);
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const uiModeSelect = document.getElementById("ui-mode-select");
const sendButton = document.getElementById("send-button");
const providerBadge = document.getElementById("provider-badge");
const a2uiDemoBtn = document.getElementById("a2ui-demo-btn");
const newChatBtn = document.getElementById("new-chat-btn");

// DOM Elements - Attachment
const attachmentFileInput = document.getElementById("attachment-file-input");
const attachFileBtn = document.getElementById("attach-file-btn");
const attachmentPreview = document.getElementById("attachment-preview");
const attachmentThumb = document.getElementById("attachment-thumb");
const attachmentDocBadge = document.getElementById("attachment-doc-badge");
const attachmentName = document.getElementById("attachment-name");
const attachmentDetails = document.getElementById("attachment-details");
const removeAttachmentBtn = document.getElementById("remove-attachment-btn");

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
const pinnedFreeModelInput = document.getElementById("pinned-free-model");
const pinnedVisionModelInput = document.getElementById("pinned-vision-model");
const clearPinnedBtn = document.getElementById("clear-pinned-btn");
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
let currentSessionId = loadOrCreateSessionId();
const logEntries = [];
let activeLogFilter = "all";
let isSending = false;
let isUploading = false;
let pendingAttachment = null;

// ---------------------------
// Logging
// ---------------------------
function formatTimestamp(date = new Date()) {
    return date.toTimeString().split(" ")[0];
}

function addLog(level, source, message, details = null) {
    const entry = {
        timestamp: formatTimestamp(),
        level,
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
        if (activeLogFilter === "error") return entry.level === "ERROR";
        if (activeLogFilter === "event") return entry.level !== "ERROR";
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
    if (shouldOpen) renderLogs();
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
        setTimeout(() => { copyLogsBtn.textContent = original; }, 1500);
    } catch (err) {
        addLog("ERROR", "LOGS", "Failed to copy logs.", err.message);
    }
}

// ---------------------------
// Multi-Session Management (SQLite)
// ---------------------------
function generateClientSessionId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
        return window.crypto.randomUUID().replace(/-/g, "");
    }
    return `sess_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

function loadOrCreateSessionId() {
    try {
        const existing = localStorage.getItem(SESSION_STORAGE_KEY);
        if (existing && existing.trim()) return existing.trim();
        const created = generateClientSessionId();
        localStorage.setItem(SESSION_STORAGE_KEY, created);
        return created;
    } catch (err) {
        return generateClientSessionId();
    }
}

async function fetchAndRenderSessions() {
    try {
        const resp = await fetch("/chat/sessions");
        if (!resp.ok) return;
        const data = await resp.json();
        const sessions = data.sessions || [];

        sessionList.innerHTML = "";
        if (sessions.length === 0) {
            const empty = document.createElement("div");
            empty.className = "session-item";
            empty.textContent = "No saved chats yet.";
            sessionList.appendChild(empty);
            return;
        }

        sessions.forEach((s) => {
            const item = document.createElement("div");
            item.className = `session-item ${s.id === currentSessionId ? "active" : ""}`;
            item.dataset.sessionId = s.id;

            const titleSpan = document.createElement("span");
            titleSpan.className = "session-item-title";
            titleSpan.textContent = s.title || "New Chat";
            titleSpan.title = s.title;

            const delBtn = document.createElement("button");
            delBtn.className = "session-delete-btn";
            delBtn.innerHTML = "&times;";
            delBtn.title = "Delete chat";
            delBtn.addEventListener("click", async (e) => {
                e.stopPropagation();
                await deleteSession(s.id);
            });

            item.appendChild(titleSpan);
            item.appendChild(delBtn);

            item.addEventListener("click", () => {
                switchSession(s.id);
            });

            sessionList.appendChild(item);
        });
    } catch (err) {
        addLog("WARN", "SESSION", "Could not load sessions list.", err.message);
    }
}

async function switchSession(sessionId) {
    if (isSending || isUploading) return;
    currentSessionId = sessionId;
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId);

    clearPendingAttachment();
    closeSettingsPage();
    if (window.innerWidth <= 768) {
        chatSidebar.classList.add("collapsed");
    }

    await restoreSessionHistory();
    fetchAndRenderSessions();
}

async function deleteSession(sessionId) {
    try {
        await fetch(`/chat/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
        addLog("INFO", "SESSION", `Deleted session: ${sessionId}`);
        if (currentSessionId === sessionId) {
            await startNewChat();
        } else {
            await fetchAndRenderSessions();
        }
    } catch (err) {
        addLog("ERROR", "SESSION", "Failed to delete session.", err.message);
    }
}

async function startNewChat() {
    if (isSending || isUploading) return;
    const previousSessionId = currentSessionId;
    currentSessionId = generateClientSessionId();
    localStorage.setItem(SESSION_STORAGE_KEY, currentSessionId);

    clearPendingAttachment();
    chatHistory.innerHTML = "";
    chatHistory.appendChild(emptyStateTemplate.cloneNode(true));
    closeSettingsPage();
    messageInput.focus();

    if (window.innerWidth <= 768) {
        chatSidebar.classList.add("collapsed");
    }

    addLog("INFO", "SESSION", "Started new chat session.", {
        previousSessionId,
        newSessionId: currentSessionId,
    });
    fetchAndRenderSessions();
}

async function restoreSessionHistory() {
    try {
        const response = await fetch(`/chat/history/${encodeURIComponent(currentSessionId)}`);
        if (!response.ok) return;
        const data = await response.json();
        const messages = data.messages || [];

        chatHistory.innerHTML = "";
        if (messages.length === 0) {
            chatHistory.appendChild(emptyStateTemplate.cloneNode(true));
        } else {
            for (const msg of messages) {
                if (msg.role === "user" || msg.role === "assistant") {
                    appendMessage(msg.role, msg.content || "");
                }
            }
        }
    } catch (err) {
        addLog("WARN", "SESSION", "Could not restore session history.", err.message);
    }
}

// ---------------------------
// Settings
// ---------------------------
function loadSettings() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return { ...DEFAULT_SETTINGS };
        const parsed = JSON.parse(raw);
        if (typeof parsed.ollamaBaseUrl === "string" && parsed.ollamaBaseUrl.includes(".cloudshell.dev")) {
            parsed.ollamaBaseUrl = "";
        }
        return { ...DEFAULT_SETTINGS, ...parsed };
    } catch (err) {
        return { ...DEFAULT_SETTINGS };
    }
}

function saveSettingsToStorage(settings) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

function getActiveModelName(settings) {
    if (settings.provider === "ollama") return settings.ollamaModel || "not selected";
    if (settings.openrouterModel === "openrouter/free" && settings.pinnedOpenRouterModel) {
        return `${settings.pinnedOpenRouterModel} (pinned)`;
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
    pinnedFreeModelInput.value = settings.pinnedOpenRouterModel || "";
    pinnedVisionModelInput.value = settings.pinnedVisionModel || "";
    ollamaBaseUrlInput.value = settings.ollamaBaseUrl || "";
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
}

function closeSettingsPage() {
    settingsView.classList.add("hidden");
    chatView.classList.remove("hidden");
    messageInput.focus();
}

function formatBytes(bytes) {
    if (!bytes || Number.isNaN(bytes)) return "";
    const gb = bytes / (1024 ** 3);
    if (gb >= 1) return `${gb.toFixed(1)} GB`;
    const mb = bytes / (1024 ** 2);
    if (mb >= 1) return `${mb.toFixed(1)} MB`;
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

async function discoverOllamaModels() {
    let baseUrl = ollamaBaseUrlInput.value.trim();
    discoverOllamaBtn.disabled = true;
    discoverOllamaBtn.textContent = "Scanning...";
    showStatusBanner(ollamaDiscoveryStatus, "Contacting Ollama...", "info");

    try {
        const endpoint = baseUrl
            ? `/api/ollama/models?base_url=${encodeURIComponent(baseUrl)}`
            : "/api/ollama/models";
        const response = await fetch(endpoint);
        const data = await response.json();

        if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);

        ollamaModelSelect.innerHTML = "";
        if (!data.models || data.models.length === 0) {
            const emptyOpt = document.createElement("option");
            emptyOpt.value = "";
            emptyOpt.textContent = "-- No local models found in Ollama --";
            ollamaModelSelect.appendChild(emptyOpt);
            showStatusBanner(ollamaDiscoveryStatus, "Connected, 0 models found.", "info");
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
        showStatusBanner(ollamaDiscoveryStatus, `Discovered ${data.count} model(s).`, "success");
    } catch (err) {
        showStatusBanner(ollamaDiscoveryStatus, `Discovery failed: ${err.message}`, "error");
    } finally {
        discoverOllamaBtn.disabled = false;
        discoverOllamaBtn.textContent = "Discover Models";
    }
}

async function clearPinnedModel() {
    currentSettings.pinnedOpenRouterModel = "";
    currentSettings.pinnedVisionModel = "";
    saveSettingsToStorage(currentSettings);
    pinnedFreeModelInput.value = "";
    pinnedVisionModelInput.value = "";
    updateHeaderBadge();
    try {
        await fetch("/chat/reset-model", { method: "POST" });
        showStatusBanner(settingsSaveFeedback, "Pinned models cleared.", "info");
    } catch (err) {}
}

// ---------------------------
// Attachments
// ---------------------------
function clearPendingAttachment() {
    pendingAttachment = null;
    attachmentFileInput.value = "";
    attachmentThumb.src = "";
    attachmentThumb.classList.add("hidden");
    attachmentDocBadge.classList.add("hidden");
    attachmentName.textContent = "";
    attachmentDetails.textContent = "";
    attachmentPreview.classList.add("hidden");
    updateSendButtonState();
}

function showPendingImage(imageInfo) {
    pendingAttachment = { kind: "image", data: imageInfo };
    attachmentDocBadge.classList.add("hidden");
    attachmentThumb.src = imageInfo.url;
    attachmentThumb.classList.remove("hidden");
    attachmentName.textContent = imageInfo.original_filename;
    attachmentDetails.textContent = `${imageInfo.width}x${imageInfo.height} · ${formatBytes(imageInfo.size_bytes)}`;
    attachmentPreview.classList.remove("hidden");
    updateSendButtonState();
}

function showPendingDocument(docInfo) {
    pendingAttachment = { kind: "document", data: docInfo };
    attachmentThumb.classList.add("hidden");
    attachmentDocBadge.textContent = (docInfo.file_type || "DOC").toUpperCase();
    attachmentDocBadge.classList.remove("hidden");
    attachmentName.textContent = docInfo.original_filename;
    const trunc = docInfo.truncated ? " · truncated" : "";
    attachmentDetails.textContent = `${docInfo.page_count} page(s) · ${docInfo.char_count.toLocaleString()} chars${trunc}`;
    attachmentPreview.classList.remove("hidden");
    updateSendButtonState();
}

async function handleAttachmentSelected(file) {
    if (!file || isUploading || isSending) return;
    const ext = "." + file.name.split(".").pop().toLowerCase();
    const isDoc = DOC_EXTENSIONS.includes(ext);
    const endpoint = isDoc ? "/upload/document" : "/upload/image";

    isUploading = true;
    attachFileBtn.disabled = true;
    updateSendButtonState();

    try {
        const formData = new FormData();
        formData.append("file", file);
        const response = await fetch(endpoint, { method: "POST", body: formData });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
        if (isDoc) showPendingDocument(data);
        else showPendingImage(data);
    } catch (err) {
        clearPendingAttachment();
        appendMessage("assistant", `Upload failed: ${err.message}`, "error");
    } finally {
        isUploading = false;
        attachFileBtn.disabled = false;
        updateSendButtonState();
    }
}

// ---------------------------
// Chat UI
// ---------------------------
function updateSendButtonState() {
    const hasText = messageInput.value.trim().length > 0;
    const hasAttachment = Boolean(pendingAttachment);
    sendButton.disabled = isSending || isUploading || (!hasText && !hasAttachment);
}

function autoResizeInput() {
    messageInput.style.height = "auto";
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 160)}px`;
}

function scrollToBottom() {
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function renderOutputIntoBubble(bubble, output) {
    bubble.innerHTML = "";
    if (output && output.text) {
        const textNode = document.createElement("div");
        textNode.textContent = output.text;
        bubble.appendChild(textNode);
    }
    if (output && output.used_a2ui && window.OracleA2uiRenderer) {
        const surfaceRoot = window.OracleA2uiRenderer.renderA2uiMessages(
            output.a2ui_messages,
            handleA2uiAction
        );
        bubble.appendChild(surfaceRoot);
    }
}

function appendMessage(role, text, extraClass = "", attachment = null, output = null) {
    const emptyEl = document.getElementById("empty-state");
    if (emptyEl) emptyEl.remove();

    const row = document.createElement("div");
    row.className = `message-row ${role}`;

    const roleLabel = document.createElement("span");
    roleLabel.className = "message-role";
    roleLabel.textContent = role === "user" ? "You" : "Assistant";

    const bubble = document.createElement("div");
    bubble.className = extraClass ? `message-bubble ${extraClass}` : "message-bubble";

    if (attachment && attachment.kind === "image" && attachment.data.url) {
        const img = document.createElement("img");
        img.className = "chat-image-preview";
        img.src = attachment.data.url;
        bubble.appendChild(img);
    } else if (attachment && attachment.kind === "document") {
        const pill = document.createElement("div");
        pill.className = "chat-doc-pill";
        pill.textContent = `[${(attachment.data.file_type || "DOC").toUpperCase()}] ${attachment.data.original_filename}`;
        bubble.appendChild(pill);
    }

    if (output) renderOutputIntoBubble(bubble, output);
    else if (text) {
        const t = document.createElement("div");
        t.textContent = text;
        bubble.appendChild(t);
    }

    row.appendChild(roleLabel);
    row.appendChild(bubble);
    chatHistory.appendChild(row);
    scrollToBottom();
    return bubble;
}

async function handleA2uiAction(actionPayload) {
    if (isSending || isUploading) return;
    const actionMessage = `UI Action "${actionPayload.name}" submitted with values: ${JSON.stringify(actionPayload.context)}`;
    await sendChatRequest({
        promptText: actionMessage,
        a2uiAction: actionPayload,
        userDisplayText: `[A2UI Action: ${actionPayload.name}] ${JSON.stringify(actionPayload.context)}`,
    });
}

async function runA2uiShowcaseDemo() {
    closeSettingsPage();
    try {
        const response = await fetch("/api/a2ui/showcase");
        const data = await response.json();
        appendMessage("assistant", "", "", null, data.output);
    } catch (err) {
        appendMessage("assistant", `Showcase error: ${err.message}`, "error");
    }
}

async function sendChatRequest({
    promptText,
    attached = null,
    a2uiAction = null,
    userDisplayText = null,
}) {
    const isVision = Boolean(attached && attached.kind === "image");
    const isDocument = Boolean(attached && attached.kind === "document");
    const uiMode = uiModeSelect.value || "auto";
    const activeProvider = currentSettings.provider || "openrouter";

    appendMessage("user", userDisplayText || promptText, "", attached);
    isSending = true;
    updateSendButtonState();

    const routerModel = activeProvider === "ollama"
        ? currentSettings.ollamaModel
        : currentSettings.openrouterModel || DEFAULT_SETTINGS.openrouterModel;

    const activePin = activeProvider === "openrouter" && routerModel === "openrouter/free"
        ? isVision ? currentSettings.pinnedVisionModel : currentSettings.pinnedOpenRouterModel
        : "";

    const effectiveDisplay = activePin || routerModel || activeProvider;
    const pendingBubble = appendMessage("assistant", `Thinking (${effectiveDisplay})...`, "pending");

    const requestBody = {
        message: promptText,
        session_id: currentSessionId,
        provider: activeProvider,
        model: routerModel,
        ui_mode: uiMode,
    };
    if (isVision) requestBody.image_id = attached.data.file_id;
    if (isDocument) {
        requestBody.document_id = attached.data.file_id;
        requestBody.document_name = attached.data.original_filename;
    }
    if (a2uiAction) requestBody.a2ui_action = a2uiAction;
    if (activeProvider === "openrouter") {
        if (currentSettings.openrouterApiKey) requestBody.api_key = currentSettings.openrouterApiKey;
    } else if (activeProvider === "ollama" && currentSettings.ollamaBaseUrl) {
        requestBody.ollama_base_url = currentSettings.ollamaBaseUrl;
    }

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(requestBody),
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);

        if (data.session_id) {
            currentSessionId = data.session_id;
            localStorage.setItem(SESSION_STORAGE_KEY, currentSessionId);
        }

        if (activeProvider === "openrouter" && routerModel === "openrouter/free" && data.model) {
            if (data.vision_used && currentSettings.pinnedVisionModel !== data.model) {
                currentSettings.pinnedVisionModel = data.model;
                saveSettingsToStorage(currentSettings);
                pinnedVisionModelInput.value = data.model;
            } else if (!data.vision_used && currentSettings.pinnedOpenRouterModel !== data.model) {
                currentSettings.pinnedOpenRouterModel = data.model;
                saveSettingsToStorage(currentSettings);
                pinnedFreeModelInput.value = data.model;
                updateHeaderBadge();
            }
        }

        pendingBubble.classList.remove("pending");
        renderOutputIntoBubble(pendingBubble, data.output);
        fetchAndRenderSessions();
    } catch (err) {
        pendingBubble.classList.remove("pending");
        pendingBubble.classList.add("error");
        pendingBubble.textContent = `Error: ${err.message}`;
    } finally {
        isSending = false;
        updateSendButtonState();
        messageInput.focus();
        scrollToBottom();
    }
}

async function handleSend(event) {
    event.preventDefault();
    const rawText = messageInput.value.trim();
    const attached = pendingAttachment;
    if ((!rawText && !attached) || isSending || isUploading) return;

    let promptText = rawText || (attached && attached.kind === "image"
        ? "Describe this image in detail."
        : "Summarize this document and list its key points.");

    messageInput.value = "";
    autoResizeInput();
    if (attached) clearPendingAttachment();

    await sendChatRequest({ promptText, attached });
}

// ---------------------------
// Event Listeners
// ---------------------------
messageInput.addEventListener("input", () => {
    autoResizeInput();
    updateSendButtonState();
});

messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (!sendButton.disabled) chatForm.requestSubmit();
    }
});

chatForm.addEventListener("submit", handleSend);

sidebarToggleBtn.addEventListener("click", () => {
    chatSidebar.classList.toggle("collapsed");
});

sidebarCloseBtn.addEventListener("click", () => {
    chatSidebar.classList.add("collapsed");
});

sidebarNewChatBtn.addEventListener("click", startNewChat);
newChatBtn.addEventListener("click", startNewChat);
a2uiDemoBtn.addEventListener("click", runA2uiShowcaseDemo);
settingsBtn.addEventListener("click", openSettingsPage);
backToChatBtn.addEventListener("click", closeSettingsPage);

attachFileBtn.addEventListener("click", () => {
    if (!isUploading && !isSending) attachmentFileInput.click();
});

attachmentFileInput.addEventListener("change", () => {
    const file = attachmentFileInput.files && attachmentFileInput.files[0];
    if (file) handleAttachmentSelected(file);
});

removeAttachmentBtn.addEventListener("click", clearPendingAttachment);

providerRadios.forEach((r) => {
    r.addEventListener("change", (e) => toggleProviderSections(e.target.value));
});

toggleKeyBtn.addEventListener("click", () => {
    const isPwd = openrouterApiKeyInput.type === "password";
    openrouterApiKeyInput.type = isPwd ? "text" : "password";
    toggleKeyBtn.textContent = isPwd ? "Hide" : "Show";
});

discoverOllamaBtn.addEventListener("click", discoverOllamaModels);
clearPinnedBtn.addEventListener("click", clearPinnedModel);

settingsForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const provider = document.querySelector('input[name="provider"]:checked').value;
    currentSettings = {
        provider,
        openrouterApiKey: openrouterApiKeyInput.value.trim(),
        openrouterModel: openrouterModelInput.value.trim() || DEFAULT_SETTINGS.openrouterModel,
        pinnedOpenRouterModel: currentSettings.pinnedOpenRouterModel,
        pinnedVisionModel: currentSettings.pinnedVisionModel,
        ollamaBaseUrl: ollamaBaseUrlInput.value.trim(),
        ollamaModel: ollamaCustomModelInput.value.trim() || ollamaModelSelect.value,
    };
    saveSettingsToStorage(currentSettings);
    updateHeaderBadge();
    showStatusBanner(settingsSaveFeedback, "Settings saved.", "success");
});

resetSettingsBtn.addEventListener("click", () => {
    currentSettings = { ...DEFAULT_SETTINGS };
    saveSettingsToStorage(currentSettings);
    populateSettingsForm(currentSettings);
    updateHeaderBadge();
    showStatusBanner(settingsSaveFeedback, "Reset to defaults.", "info");
});

logsToggleBtn.addEventListener("click", () => toggleLogDrawer());
openLogsFromSettingsBtn.addEventListener("click", () => toggleLogDrawer(true));
closeLogsBtn.addEventListener("click", () => toggleLogDrawer(false));
copyLogsBtn.addEventListener("click", copyLogsToClipboard);
clearLogsBtn.addEventListener("click", () => {
    logEntries.length = 0;
    renderLogs();
});

logFilterButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
        activeLogFilter = btn.dataset.filter;
        logFilterButtons.forEach((b) => b.classList.toggle("active", b === btn));
        renderLogs();
    });
});

// Initialization
updateHeaderBadge();
restoreSessionHistory();
fetchAndRenderSessions();
