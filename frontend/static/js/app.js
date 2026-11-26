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
// Event & Error Logging
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
// Session Management
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
        if (existing && existing.trim()) {
            return existing.trim();
        }
        const created = generateClientSessionId();
        localStorage.setItem(SESSION_STORAGE_KEY, created);
        return created;
    } catch (err) {
        return generateClientSessionId();
    }
}

async function startNewChat() {
    if (isSending || isUploading) {
        return;
    }

    const previousSessionId = currentSessionId;
    currentSessionId = generateClientSessionId();
    try {
        localStorage.setItem(SESSION_STORAGE_KEY, currentSessionId);
    } catch (err) {
        // Ignore storage errors
    }

    clearPendingAttachment();
    chatHistory.innerHTML = "";
    chatHistory.appendChild(emptyStateTemplate.cloneNode(true));
    closeSettingsPage();
    messageInput.focus();

    try {
        await fetch(`/chat/history/${encodeURIComponent(previousSessionId)}`, {
            method: "DELETE",
        });
    } catch (err) {
        // Ignore cleanup errors
    }

    addLog("INFO", "SESSION", "Started new chat session.", {
        previousSessionId,
        newSessionId: currentSessionId,
    });
}

async function restoreSessionHistory() {
    try {
        const response = await fetch(`/chat/history/${encodeURIComponent(currentSessionId)}`);
        if (!response.ok) {
            return;
        }
        const data = await response.json();
        const messages = data.messages || [];
        if (messages.length > 0) {
            chatHistory.innerHTML = "";
            for (const msg of messages) {
                if (msg.role === "user" || msg.role === "assistant") {
                    appendMessage(msg.role, msg.content || "");
                }
            }
            addLog("INFO", "SESSION", "Restored session conversation history.", {
                sessionId: currentSessionId,
                messagesCount: messages.length,
            });
        }
    } catch (err) {
        addLog("WARN", "SESSION", "Could not restore session history.", err.message);
    }
}

// ---------------------------
// Settings Management
// ---------------------------
function loadSettings() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) {
            return { ...DEFAULT_SETTINGS };
        }
        const parsed = JSON.parse(raw);
        if (parsed.openrouterModel === "google/gemma-4-31b-it:free") {
            parsed.openrouterModel = DEFAULT_SETTINGS.openrouterModel;
        }
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
    if (settings.provider === "ollama") {
        return settings.ollamaModel || "not selected";
    }
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
    addLog("INFO", "UI", "Opened Settings page.");
}

function closeSettingsPage() {
    settingsView.classList.add("hidden");
    chatView.classList.remove("hidden");
    messageInput.focus();
}

function formatBytes(bytes) {
    if (!bytes || Number.isNaN(bytes)) {
        return "";
    }
    const gb = bytes / (1024 ** 3);
    if (gb >= 1) {
        return `${gb.toFixed(1)} GB`;
    }
    const mb = bytes / (1024 ** 2);
    if (mb >= 1) {
        return `${mb.toFixed(1)} MB`;
    }
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

async function discoverOllamaModels() {
    let baseUrl = ollamaBaseUrlInput.value.trim();
    if (baseUrl.includes(".cloudshell.dev")) {
        baseUrl = "";
        ollamaBaseUrlInput.value = "";
        addLog("INFO", "OLLAMA", "Cleared Cloud Shell preview URL; using backend local OLLAMA_BASE_URL.");
    }

    discoverOllamaBtn.disabled = true;
    discoverOllamaBtn.textContent = "Scanning...";
    showStatusBanner(
        ollamaDiscoveryStatus,
        `Contacting Ollama (${baseUrl || "backend local default"})...`,
        "info"
    );
    addLog("INFO", "OLLAMA", `Starting dynamic model discovery (${baseUrl || "backend default"})`);

    try {
        const endpoint = baseUrl
            ? `/api/ollama/models?base_url=${encodeURIComponent(baseUrl)}`
            : "/api/ollama/models";
        const response = await fetch(endpoint);
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
                `Connected to Ollama at ${data.base_url}, but 0 models were returned. Pull a model first.`,
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

async function clearPinnedModel() {
    currentSettings.pinnedOpenRouterModel = "";
    currentSettings.pinnedVisionModel = "";
    saveSettingsToStorage(currentSettings);
    pinnedFreeModelInput.value = "";
    pinnedVisionModelInput.value = "";
    updateHeaderBadge();

    try {
        await fetch("/chat/reset-model", { method: "POST" });
        showStatusBanner(
            settingsSaveFeedback,
            "Pinned free text & vision models cleared. Next requests will ask openrouter/free to assign new models.",
            "info"
        );
        addLog("INFO", "SETTINGS", "Cleared pinned OpenRouter text & vision models.");
    } catch (err) {
        addLog("WARN", "SETTINGS", "Cleared browser pins; backend reset failed.", err.message);
    }
}

// ---------------------------
// Image & Document Upload Preview
// ---------------------------
function clearPendingAttachment() {
    pendingAttachment = null;
    attachmentFileInput.value = "";
    attachmentThumb.src = "";
    attachmentThumb.classList.add("hidden");
    attachmentDocBadge.textContent = "DOC";
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
    attachmentThumb.src = "";
    attachmentDocBadge.textContent = (docInfo.file_type || "DOC").toUpperCase();
    attachmentDocBadge.classList.remove("hidden");
    attachmentName.textContent = docInfo.original_filename;
    const truncNote = docInfo.truncated ? " · truncated" : "";
    attachmentDetails.textContent = `${docInfo.page_count} page(s) · ${docInfo.char_count.toLocaleString()} chars · ${formatBytes(docInfo.size_bytes)}${truncNote}`;
    attachmentPreview.classList.remove("hidden");
    updateSendButtonState();
}

function getFileExtension(filename) {
    const idx = filename.lastIndexOf(".");
    return idx >= 0 ? filename.slice(idx).toLowerCase() : "";
}

async function handleAttachmentSelected(file) {
    if (!file || isUploading || isSending) {
        return;
    }

    const ext = getFileExtension(file.name);
    const isImage = IMAGE_EXTENSIONS.includes(ext) || file.type.startsWith("image/");
    const isDoc = DOC_EXTENSIONS.includes(ext);

    if (!isImage && !isDoc) {
        const msg = `Unsupported file "${file.name}". Allowed: JPG, JPEG, PNG, WEBP, PDF, TXT.`;
        appendMessage("assistant", msg, "error");
        addLog("ERROR", "UPLOAD", msg);
        attachmentFileInput.value = "";
        return;
    }

    const endpoint = isDoc ? "/upload/document" : "/upload/image";
    isUploading = true;
    attachFileBtn.disabled = true;
    updateSendButtonState();

    addLog("INFO", "UPLOAD", `Uploading ${isDoc ? "document" : "image"}...`, {
        filename: file.name,
        size: file.size,
        endpoint,
    });

    try {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch(endpoint, {
            method: "POST",
            body: formData,
        });

        let data = null;
        try {
            data = await response.json();
        } catch (parseErr) {
            throw new Error(`Invalid JSON response (HTTP ${response.status})`);
        }

        if (!response.ok) {
            throw new Error(extractApiErrorMessage(data, response.status));
        }

        if (isDoc) {
            showPendingDocument(data);
            addLog("INFO", "UPLOAD", "Document uploaded & text extracted.", {
                fileId: data.file_id,
                fileType: data.file_type,
                pages: data.page_count,
                chars: data.char_count,
                truncated: data.truncated,
            });
        } else {
            showPendingImage(data);
            addLog("INFO", "UPLOAD", "Image uploaded and stored.", {
                fileId: data.file_id,
                url: data.url,
                dimensions: `${data.width}x${data.height}`,
                sizeBytes: data.size_bytes,
            });
        }
    } catch (err) {
        clearPendingAttachment();
        appendMessage("assistant", `Upload failed: ${err.message}`, "error");
        addLog("ERROR", "UPLOAD", "File upload failed.", err.message);
    } finally {
        isUploading = false;
        attachFileBtn.disabled = false;
        updateSendButtonState();
    }
}

// ---------------------------
// Chat UI & Standardized Pydantic + A2UI Rendering
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
    const text = output && output.text ? output.text : "";
    if (text) {
        const textNode = document.createElement("div");
        textNode.textContent = text;
        bubble.appendChild(textNode);
    }

    if (
        output &&
        output.used_a2ui &&
        Array.isArray(output.a2ui_messages) &&
        output.a2ui_messages.length > 0 &&
        window.OracleA2uiRenderer
    ) {
        const surfaceRoot = window.OracleA2uiRenderer.renderA2uiMessages(
            output.a2ui_messages,
            handleA2uiAction
        );
        bubble.appendChild(surfaceRoot);
    }
}

function appendMessage(role, text, extraClass = "", attachment = null, output = null) {
    const emptyEl = document.getElementById("empty-state");
    if (emptyEl && emptyEl.parentNode) {
        emptyEl.remove();
    }

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
        img.alt = attachment.data.original_filename || "Uploaded image";
        bubble.appendChild(img);

        const caption = document.createElement("span");
        caption.className = "chat-image-caption";
        caption.textContent = `${attachment.data.original_filename} (${attachment.data.width}x${attachment.data.height})`;
        bubble.appendChild(caption);
    } else if (attachment && attachment.kind === "document") {
        const pill = document.createElement("div");
        pill.className = "chat-doc-pill";

        const tag = document.createElement("span");
        tag.className = "chat-doc-tag";
        tag.textContent = attachment.data.file_type || "DOC";

        const name = document.createElement("span");
        name.textContent = `${attachment.data.original_filename} (${attachment.data.page_count}p · ${attachment.data.char_count.toLocaleString()} chars)`;

        pill.appendChild(tag);
        pill.appendChild(name);
        bubble.appendChild(pill);
    }

    if (output) {
        renderOutputIntoBubble(bubble, output);
    } else if (text) {
        const textNode = document.createElement("div");
        textNode.textContent = text;
        bubble.appendChild(textNode);
    }

    row.appendChild(roleLabel);
    row.appendChild(bubble);
    chatHistory.appendChild(row);
    scrollToBottom();

    return bubble;
}

function extractApiErrorMessage(data, statusCode) {
    if (!data) {
        return `HTTP ${statusCode}`;
    }
    if (typeof data.detail === "string") {
        return data.detail;
    }
    if (Array.isArray(data.detail) && data.detail.length > 0) {
        return data.detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
    }
    return `HTTP ${statusCode}`;
}

async function runA2uiShowcaseDemo() {
    closeSettingsPage();
    addLog("INFO", "A2UI", "Requesting 18-element A2UI showcase from /api/a2ui/showcase...");
    try {
        const response = await fetch("/api/a2ui/showcase");
        const data = await response.json();
        if (!response.ok) {
            throw new Error(extractApiErrorMessage(data, response.status));
        }
        appendMessage("assistant", "", "", null, data.output);
        addLog("INFO", "A2UI", "Rendered A2UI 18-element showcase.", {
            componentCount: data.component_count,
            components: data.components_supported,
        });
    } catch (err) {
        appendMessage("assistant", `A2UI Demo error: ${err.message}`, "error");
        addLog("ERROR", "A2UI", "Failed to load A2UI showcase.", err.message);
    }
}

async function handleA2uiAction(actionPayload) {
    addLog("INFO", "A2UI_ACTION", `Triggered action '${actionPayload.name}'`, actionPayload);
    if (isSending || isUploading) {
        return;
    }

    const actionMessage = `UI Action "${actionPayload.name}" submitted with values: ${JSON.stringify(actionPayload.context)}`;
    await sendChatRequest({
        promptText: actionMessage,
        a2uiAction: actionPayload,
        userDisplayText: `[A2UI Action: ${actionPayload.name}] ${JSON.stringify(actionPayload.context)}`,
    });
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

    const routerModel =
        activeProvider === "ollama"
            ? currentSettings.ollamaModel
            : currentSettings.openrouterModel || DEFAULT_SETTINGS.openrouterModel;

    const activePin =
        activeProvider === "openrouter" && routerModel === "openrouter/free"
            ? isVision
                ? currentSettings.pinnedVisionModel
                : currentSettings.pinnedOpenRouterModel
            : "";

    const effectiveDisplay = activePin || routerModel || activeProvider;

    const statusText = isVision
        ? `Analyzing image (${effectiveDisplay})...`
        : isDocument
          ? `Reading document (${effectiveDisplay})...`
          : `Thinking (${effectiveDisplay})...`;
    const pendingBubble = appendMessage("assistant", statusText, "pending");

    const requestBody = {
        message: promptText,
        session_id: currentSessionId,
        provider: activeProvider,
        model: routerModel,
        ui_mode: uiMode,
    };
    if (isVision) {
        requestBody.image_id = attached.data.file_id;
    }
    if (isDocument) {
        requestBody.document_id = attached.data.file_id;
        requestBody.document_name = attached.data.original_filename;
    }
    if (a2uiAction) {
        requestBody.a2ui_action = a2uiAction;
    }
    if (activeProvider === "openrouter") {
        if (routerModel === "openrouter/free") {
            if (isVision && currentSettings.pinnedVisionModel) {
                requestBody.pinned_vision_model = currentSettings.pinnedVisionModel;
            } else if (!isVision && currentSettings.pinnedOpenRouterModel) {
                requestBody.pinned_model = currentSettings.pinnedOpenRouterModel;
            }
        }
        if (currentSettings.openrouterApiKey) {
            requestBody.api_key = currentSettings.openrouterApiKey;
        }
    } else if (activeProvider === "ollama" && currentSettings.ollamaBaseUrl) {
        requestBody.ollama_base_url = currentSettings.ollamaBaseUrl;
    }

    const logSource = isVision ? "VISION" : isDocument ? "DOCUMENT" : "CHAT";
    addLog("INFO", logSource, "POST /chat request sent.", {
        sessionId: currentSessionId,
        provider: activeProvider,
        model: routerModel || null,
        uiMode,
        vision: isVision,
        document: isDocument,
        hasAction: Boolean(a2uiAction),
        pinnedModel: activePin || null,
    });

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(requestBody),
        });

        let data = null;
        try {
            data = await response.json();
        } catch (parseErr) {
            throw new Error(`Invalid JSON response (HTTP ${response.status})`);
        }

        if (!response.ok) {
            throw new Error(extractApiErrorMessage(data, response.status));
        }

        if (data.session_id) {
            currentSessionId = data.session_id;
            localStorage.setItem(SESSION_STORAGE_KEY, currentSessionId);
        }

        if (
            activeProvider === "openrouter" &&
            routerModel === "openrouter/free" &&
            data.model &&
            data.model !== "openrouter/free"
        ) {
            if (data.vision_used) {
                if (currentSettings.pinnedVisionModel !== data.model) {
                    currentSettings.pinnedVisionModel = data.model;
                    saveSettingsToStorage(currentSettings);
                    pinnedVisionModelInput.value = data.model;
                    addLog("INFO", "OPENROUTER", `Assigned & pinned free vision model: ${data.model}`);
                }
            } else if (currentSettings.pinnedOpenRouterModel !== data.model) {
                currentSettings.pinnedOpenRouterModel = data.model;
                saveSettingsToStorage(currentSettings);
                pinnedFreeModelInput.value = data.model;
                updateHeaderBadge();
                addLog("INFO", "OPENROUTER", `Assigned & pinned free model: ${data.model}`);
            }
        }

        pendingBubble.classList.remove("pending");
        const standardized = data.output || { text: data.reply ?? "", used_a2ui: false, a2ui_messages: [] };
        renderOutputIntoBubble(pendingBubble, standardized);

        if (standardized.repair_retried && standardized.used_a2ui) {
            addLog("INFO", "A2UI", "Auto-repaired A2UI syntax on 1-retry.");
        }
        if (Array.isArray(standardized.validation_warnings) && standardized.validation_warnings.length > 0) {
            addLog("WARN", "A2UI", "Fallback to plain text after A2UI validation warning.", standardized.validation_warnings);
        }

        addLog("INFO", logSource, "Received standardized reply.", {
            sessionId: data.session_id,
            historyLength: data.history_length,
            provider: data.provider || activeProvider,
            model: data.model || effectiveDisplay,
            usedA2ui: Boolean(standardized.used_a2ui),
            repairRetried: Boolean(standardized.repair_retried),
            rawFormat: standardized.raw_format,
            a2uiMessages: (standardized.a2ui_messages || []).length,
        });
    } catch (err) {
        pendingBubble.classList.remove("pending");
        pendingBubble.classList.add("error");
        pendingBubble.textContent = `Error: ${err.message}`;
        addLog("ERROR", logSource, `${activeProvider} request failed.`, err.message);
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

    if ((!rawText && !attached) || isSending || isUploading) {
        return;
    }

    const isVision = Boolean(attached && attached.kind === "image");
    let promptText = rawText;
    if (!promptText) {
        promptText = isVision
            ? "Describe this image in detail."
            : "Summarize this document and list its key points.";
    }

    messageInput.value = "";
    autoResizeInput();
    if (attached) {
        clearPendingAttachment();
    }

    await sendChatRequest({ promptText, attached });
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

attachFileBtn.addEventListener("click", () => {
    if (!isUploading && !isSending) {
        attachmentFileInput.click();
    }
});

attachmentFileInput.addEventListener("change", () => {
    const file = attachmentFileInput.files && attachmentFileInput.files[0];
    if (file) {
        handleAttachmentSelected(file);
    }
});

removeAttachmentBtn.addEventListener("click", () => {
    if (pendingAttachment) {
        addLog(
            "INFO",
            "UPLOAD",
            `Removed attached ${pendingAttachment.kind} before sending.`,
            pendingAttachment.data.original_filename
        );
    }
    clearPendingAttachment();
});

chatForm.addEventListener("submit", handleSend);

a2uiDemoBtn.addEventListener("click", runA2uiShowcaseDemo);
newChatBtn.addEventListener("click", startNewChat);
settingsBtn.addEventListener("click", openSettingsPage);
backToChatBtn.addEventListener("click", () => {
    closeSettingsPage();
    addLog("INFO", "UI", "Returned to Chat view.");
});

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
clearPinnedBtn.addEventListener("click", clearPinnedModel);

ollamaModelSelect.addEventListener("change", () => {
    if (ollamaModelSelect.value) {
        ollamaCustomModelInput.value = ollamaModelSelect.value;
    }
});

settingsForm.addEventListener("submit", (event) => {
    event.preventDefault();

    const selectedProvider = document.querySelector('input[name="provider"]:checked').value;
    const enteredOpenRouterModel = openrouterModelInput.value.trim() || DEFAULT_SETTINGS.openrouterModel;
    const enteredOllamaUrl = ollamaBaseUrlInput.value.trim();

    const updated = {
        provider: selectedProvider,
        openrouterApiKey: openrouterApiKeyInput.value.trim(),
        openrouterModel: enteredOpenRouterModel,
        pinnedOpenRouterModel:
            enteredOpenRouterModel === "openrouter/free"
                ? currentSettings.pinnedOpenRouterModel
                : "",
        pinnedVisionModel:
            enteredOpenRouterModel === "openrouter/free"
                ? currentSettings.pinnedVisionModel
                : "",
        ollamaBaseUrl: enteredOllamaUrl.includes(".cloudshell.dev") ? "" : enteredOllamaUrl,
        ollamaModel: ollamaCustomModelInput.value.trim() || ollamaModelSelect.value,
    };

    if (selectedProvider === "openrouter" && !updated.openrouterApiKey) {
        addLog("WARN", "SETTINGS", "Saved OpenRouter provider without UI key (will use backend .env if set).");
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
        ollamaBaseUrl: currentSettings.ollamaBaseUrl || "backend default",
    });
});

resetSettingsBtn.addEventListener("click", async () => {
    currentSettings = { ...DEFAULT_SETTINGS };
    saveSettingsToStorage(currentSettings);
    populateSettingsForm(currentSettings);
    updateHeaderBadge();
    try {
        await fetch("/chat/reset-model", { method: "POST" });
    } catch (err) {
        // Ignore network errors during reset
    }
    showStatusBanner(settingsSaveFeedback, "Settings reset to defaults (openrouter/free).", "info");
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
    sessionId: currentSessionId,
    provider: currentSettings.provider,
    model: getActiveModelName(currentSettings),
});
restoreSessionHistory();
