#!/usr/bin/env bash
set -euo pipefail

APP_USER="${SUDO_USER:-$USER}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_PORT="${APP_PORT:-8080}"
PULL_MODELS="${PULL_MODELS:-false}"

echo "=== ORACLE_CHAT Production Setup ==="
echo "User:      ${APP_USER}"
echo "Directory: ${APP_DIR}"
echo "Port:      ${APP_PORT}"

echo "[1/6] Installing Python, Git, zstd, and firewall tools..."
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-venv python3-pip git curl zstd ufw iptables-persistent

echo "[2/6] Setting up Python virtual environment and dependencies..."
cd "${APP_DIR}"
if [ ! -d "${APP_DIR}/venv" ]; then
    python3 -m venv "${APP_DIR}/venv"
fi
"${APP_DIR}/venv/bin/pip" install --upgrade pip
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "[3/6] Ensuring .env configuration exists..."
if [ ! -f "${APP_DIR}/.env" ]; then
    cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
    echo "Created .env from .env.example — remember to add your OPENROUTER_API_KEY or set LLM_PROVIDER=ollama."
fi

echo "[4/6] Installing and enabling Ollama..."
if ! command -v ollama >/dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh
fi
sudo systemctl enable ollama
sudo systemctl restart ollama

if [ "${PULL_MODELS}" = "true" ]; then
    echo "Pulling gemma3:4b (this may take a few minutes)..."
    ollama pull gemma3:4b
fi

echo "[5/6] Configuring OS firewall (iptables + ufw) for SSH (22) and App (${APP_PORT})..."
sudo ufw allow OpenSSH >/dev/null 2>&1 || true
sudo ufw allow "${APP_PORT}/tcp" >/dev/null 2>&1 || true
sudo iptables -C INPUT -p tcp --dport "${APP_PORT}" -j ACCEPT 2>/dev/null || \
    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport "${APP_PORT}" -j ACCEPT
sudo netfilter-persistent save >/dev/null 2>&1 || true

echo "[6/6] Installing and starting systemd service (oracle-chat.service)..."
TMP_UNIT="/tmp/oracle-chat.service"
sed \
    -e "s|__APP_USER__|${APP_USER}|g" \
    -e "s|__APP_DIR__|${APP_DIR}|g" \
    -e "s|__APP_PORT__|${APP_PORT}|g" \
    "${APP_DIR}/deploy/oracle-chat.service" > "${TMP_UNIT}"

sudo cp "${TMP_UNIT}" /etc/systemd/system/oracle-chat.service
rm -f "${TMP_UNIT}"
sudo systemctl daemon-reload
sudo systemctl enable oracle-chat
sudo systemctl restart oracle-chat

echo "=== Setup Complete ==="
echo "Check service status: sudo systemctl status oracle-chat"
echo "Follow live logs:     sudo journalctl -u oracle-chat -f"
echo "Test locally:         curl -s http://localhost:${APP_PORT}/health"
