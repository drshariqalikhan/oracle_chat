# ORACLE_CHAT

Self-hosted AI chat application designed for development in Google Cloud Shell and deployment on Oracle Cloud Always Free VM.

See `PLAN.md` for the full architecture and milestone roadmap.

## Quick Start (Milestone 0)

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
