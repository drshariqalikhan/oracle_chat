# ORACLE_CHAT

Self-hosted AI chat application designed for development in Google Cloud Shell and deployment on Oracle Cloud Always Free VM.

See `PLAN.md` for the full architecture and milestone roadmap.

## Quick Start (Milestone 0)

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload


he cleanest and fastest way is to generate a single bundled text file of all your current code files right from Google Cloud Shell.
Run this one-liner in your Google Cloud Shell terminal:
Bash
cd ~/oracle_chat
git pull origin main

python3 -c "
import subprocess

files = subprocess.check_output(['git', 'ls-files']).decode().splitlines()
skip_ext = {'.png', '.jpg', '.jpeg', '.webp', '.pdf', '.keep'}

with open('project_dump.txt', 'w', encoding='utf-8') as out:
    for f in sorted(files):
        if any(f.endswith(ext) for ext in skip_ext):
            continue
        out.write(f'=== FILE: {f} ===\n')
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                out.write(fh.read())
        except Exception as e:
            out.write(f'ERROR: {e}\n')
        out.write('\n=== END FILE ===\n\n')

print('Export complete! Check project_dump.txt')
"
