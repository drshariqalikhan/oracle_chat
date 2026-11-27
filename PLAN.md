# ORACLE_CHAT PROJECT PLAN

Repository:
https://github.com/drshariqalikhan/oracle_chat

Author:
Dr Shariq Ali Khan

Primary Development Environment:
Google Cloud Shell

Source Control:
GitHub (single source of truth)

Target Deployment:
Oracle Cloud Always Free VM

Long-Term Goal:
A self-hosted AI assistant, Telegram bot, and modular API -> local Ollama pipeline platform.

---

# 1. PROJECT VISION

ORACLE_CHAT runs on an Oracle Cloud Always Free ARM VM (`2 OCPUs`, `12 GB RAM`) with:

- Interactive Web UI (FastAPI + SQLite + A2UI v1.0 + OpenRouter/Ollama)
- Interactive Telegram Bot (`bot/main.py` via `oracle-bot.service`)
- Active Background Quote Pipeline (`pipeline/runner.py` + `configs/quote_pipeline.json` via `oracle-quote-bot.service`)
- Staged Google Trends Pipeline (`trends_pipeline/runner.py` + `configs/google_trends_pipeline.json` — testing before swapping)
- Standalone SEC EDGAR fundamental script (`scripts/edgar_fetch.py`)

---

# 2. DEVELOPMENT CONSTRAINTS

1. Developer is a hobby coder.
2. Development occurs entirely inside Google Cloud Shell.
3. No local development PC workflow.
4. GitHub is the source of truth.
5. All code changes are provided as executable Bash commands using `cat << 'EOF' > filename`.
6. Never provide partial file contents; always provide complete files.
7. Every milestone ends with a working state, test instructions, and Git commit/push.

---

# 3. HIGH LEVEL ARCHITECTURE

External APIs (Quote API / Bright Data Google Trends API / SEC EDGAR)
    ↓
Pipeline Workers (`pipeline/` [active] & `trends_pipeline/` [staged])
    ↓
Local Ollama (`gemma4:e4b-it-qat`)
    ↓
Telegram Notification + SQLite Feedback (`data/quote_feedback.db`)
    ↑
Interactive Telegram Bot (`bot/main.py`) & Web UI (`backend/main.py`)

---

# 4. CURRENT PIPELINES & SERVICES

- `oracle-chat.service` -> FastAPI Web UI (`backend.main:app`, port `8080`)
- `oracle-bot.service` -> Interactive Telegram bot (`bot/main.py`)
- `oracle-quote-bot.service` -> Currently running `pipeline.runner configs/quote_pipeline.json` untouched
- `trends_pipeline/runner.py` -> Isolated Google Trends pipeline (`configs/google_trends_pipeline.json`) for testing before swapping
- `scripts/edgar_fetch.py` -> Standalone SEC EDGAR + XBRL fetcher (no AI)

---

# 5. CODING AI INSTRUCTIONS

- Provide executable Bash only for code changes.
- Use `cat << 'EOF'` for complete files.
- Preserve existing working services until staged replacements are verified.
- Update `PLAN.md` whenever significant changes happen.
- End with testing steps and Git commit & push instructions.
