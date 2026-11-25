const chatHistory = document.getElementById("chat-history");
const emptyState = document.getElementById("empty-state");
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");

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

    messageInput.value = "";
    autoResizeInput();
    updateSendButtonState();
    messageInput.focus();

    // Milestone 1: Frontend-only preview response (Backend connected in Milestone 2)
    appendMessage("assistant", `UI Preview received: "${text}"`);
}

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
