# ORACLE_CHAT PROJECT PLAN#

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
A self-hosted AI chat application with support for:

- Chat
- Image upload
- Vision-capable LLMs
- PDF and document upload
- Multiple interchangeable LLM providers
- Local Ollama models
- Agent extensions in future releases

---

# 1. PROJECT VISION

ORACLE_CHAT is intended to be a lightweight, self-hosted AI assistant platform that is developed entirely in Google Cloud Shell and deployed later to an Oracle Always Free VM.

The system should support:

- Text chat
- Image understanding
- Document understanding
- Multiple LLM providers
- Local LLM inference through Ollama
- Future agentic workflows

The architecture must prioritize simplicity, maintainability, and swap-able AI providers.

---

# 2. DEVELOPMENT CONSTRAINTS

The coding AI must always assume:

1. Developer is a hobby coder.
2. Development occurs entirely inside Google Cloud Shell.
3. No local development PC workflow.
4. GitHub is the source of truth.
5. All code changes should be provided as executable Bash commands.
6. Files should be created using:

   cat << 'EOF' > filename

7. Never provide partial file contents.
8. Always provide complete file contents.
9. Every milestone should end with a working application state.
10. Commit and push after every milestone.

---

# 3. HIGH LEVEL ARCHITECTURE

Browser
    ↓
Web Chat Interface
    ↓
FastAPI Backend
    ↓
Provider Abstraction Layer
        ↓
        OpenRouter
        Ollama
        Future Providers
    ↓
Selected Model

---

# 4. TECHNOLOGY STACK

Frontend

- HTML
- CSS
- Vanilla JavaScript

Backend

- Python
- FastAPI
- Uvicorn

AI Providers

- OpenRouter
- Ollama

File Processing

- Pillow
- PyPDF

Version Control

- Git
- GitHub

Future Components

- SQLite
- Vector Database
- Agent Framework
- Authentication Layer

---

# 5. PROJECT DIRECTORY STRUCTURE

oracle_chat/

├── app/
│
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   │
│   ├── llm/
│   │   ├── base.py
│   │   ├── openrouter.py
│   │   └── ollama.py
│   │
│   ├── routes/
│   │   ├── chat.py
│   │   ├── upload.py
│   │   └── health.py
│   │
│   └── services/
│       ├── file_service.py
│       └── image_service.py
│
├── frontend/
│   ├── templates/
│   │   └── index.html
│   │
│   └── static/
│       ├── css/
│       │   └── style.css
│       │
│       └── js/
│           └── app.js
│
├── uploads/
│
├── tests/
│
├── requirements.txt
├── .env.example
├── README.md
├── PLAN.md
└── .gitignore

---

# 6. DEVELOPMENT PHILOSOPHY

The project must be developed using incremental milestones.

Each milestone should:

- Produce a working application
- Be independently testable
- Be committed to GitHub
- Preserve compatibility with future milestones

No milestone should require major rewrites of earlier milestones.

---

# 7. MILESTONE ROADMAP

## MILESTONE 0
Repository Bootstrap

Goal:
Create base project structure and verify FastAPI works.

Deliverables:
- Folder structure
- requirements.txt
- main.py
- Home route
- Uvicorn launch

Success Criteria:
Browser displays:

ORACLE CHAT
System Online

Git Commit:

milestone-0-bootstrap

---

## MILESTONE 1
Modern Chat Interface

Goal:
Create ChatGPT-style frontend.

Features:

- Header
- Chat history
- User messages
- Assistant messages
- Input field
- Send button

Backend:
No AI connection.

Success Criteria:
Messages display in browser.

Git Commit:

milestone-1-chat-ui

---

## MILESTONE 2
Frontend ↔ Backend Integration

Goal:
Connect UI to FastAPI.

Endpoint:

POST /chat

Request:

{
  "message": "hello"
}

Response:

{
  "reply": "message received"
}

Success Criteria:
Backend receives and returns messages.

Git Commit:

milestone-2-chat-api

---

## MILESTONE 3
OpenRouter Integration

Goal:
Connect first LLM.

Files:

backend/llm/base.py

backend/llm/openrouter.py

Environment Variable:

OPENROUTER_API_KEY

Success Criteria:
Messages routed through OpenRouter.

Git Commit:

milestone-3-openrouter

---

## MILESTONE 4
Conversation Memory

Goal:
Maintain conversation history.

Features:

- Session-based memory
- Message history

Success Criteria:
Model remembers earlier messages.

Git Commit:

milestone-4-memory

---

## MILESTONE 5
Image Upload

Goal:
Allow image uploads.

Supported Types:

- jpg
- jpeg
- png
- webp

Features:

- Upload image
- Store image
- Display preview

Success Criteria:
Image visible inside chat flow.

Git Commit:

milestone-5-image-upload

---

## MILESTONE 6
Vision Support

Goal:
Analyze images using multimodal LLM.

Workflow:

Upload image
→ Vision model
→ Analysis returned

Success Criteria:
Image descriptions generated.

Git Commit:

milestone-6-vision

---

## MILESTONE 7
Document Upload

Goal:
Support:

- PDF
- TXT

Workflow:

Upload
→ Extract Text
→ Send To Model

Success Criteria:
Questions can be answered about documents.

Git Commit:

milestone-7-documents

---

## MILESTONE 8
Provider Abstraction Layer

Goal:
Support multiple inference providers.

Create Interface:

LLMProvider

Methods:

- chat()
- analyze_image()
- process_document()

Implementations:

- OpenRouterProvider
- OllamaProvider

Success Criteria:

Backend can switch providers through configuration.

Git Commit:

milestone-8-provider-abstraction

---

## MILESTONE 9
Ollama Integration

Goal:
Connect local models.

Example Models:

- gemma3:4b
- qwen2.5-vl

Success Criteria:
Application works against local Ollama API.

Git Commit:

milestone-9-ollama

---

## MILESTONE 10
Oracle VM Deployment

Goal:
Deploy production environment.

Tasks:

- Install Python
- Install Ollama
- Configure Firewall
- Configure Environment Variables
- Configure Startup Service

Success Criteria:
Public deployment operational.

Git Commit:

milestone-10-oracle-deployment

---

## MILESTONE 11
Runtime Model Switching

Goal:
Switch providers and models without code changes.

Examples:

LLM_PROVIDER=openrouter

MODEL_NAME=google/gemma-4-31b-it:free

OR

LLM_PROVIDER=ollama

MODEL_NAME=qwen2.5-vl

Success Criteria:
Only environment variables change.

Git Commit:

milestone-11-model-switching

---

# 8. TESTING STRATEGY

Each milestone must include:

- Startup verification
- Browser verification
- API verification
- Error handling verification

The application must never regress.

---

# 9. DEPLOYMENT STRATEGY

Development Environment:

Google Cloud Shell

Production Environment:

Oracle Cloud Always Free VM

Inference Strategy:

Development:
OpenRouter

Production:
Ollama

Fallback:
OpenRouter

The application should be deployable without major code changes.

---

# 10. FUTURE ROADMAP

Phase A
Authentication

Phase B
SQLite Chat Storage

Phase C
Multiple Chat Sessions

Phase D
Retrieval-Augmented Generation (RAG)

Phase E
Voice Input

Phase F
Text-To-Speech

Phase G
WhatsApp Integration

Phase H
Telegram Integration

Phase I
Agent Framework

Phase J
Tool Calling

Phase K
Autonomous Task Execution

---

# 11. CODING AI INSTRUCTIONS

When generating code:

- Provide executable Bash only.
- Use cat << 'EOF' for files.
- Output complete files.
- Preserve project architecture.
- Avoid unnecessary rewrites.
- Maintain milestone compatibility.
- Ensure every milestone remains deployable.
- Always end with Git commit instructions.
- Always explain how to test the milestone.

