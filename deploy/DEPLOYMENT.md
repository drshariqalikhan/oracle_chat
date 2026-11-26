# ORACLE_CHAT — Oracle Cloud Always Free VM Deployment Guide

## 1. Provision Oracle Always Free VM
1. In Oracle Cloud Console (OCI), create an instance:
   - **Image:** Ubuntu 22.04 or 24.04 (Canonical Ubuntu)
   - **Shape:** `VM.Standard.A1.Flex` (Always Free ARM: up to 4 OCPUs, 24 GB RAM)
   - **Boot Volume:** 50 GB–100 GB (Always Free includes up to 200 GB total)
2. Open port `8080` in OCI Networking:
   - Go to **Networking -> Virtual Cloud Networks -> Your VCN -> Security Lists -> Default Security List**.
   - Click **Add Ingress Rules**:
     - **Source CIDR:** `0.0.0.0/0`
     - **IP Protocol:** `TCP`
     - **Destination Port Range:** `8080`
   - Do **not** open port `11434` publicly; FastAPI communicates with Ollama over `localhost`.

## 2. Clone & Configure on the Oracle VM
SSH into your Oracle VM and run:

    git clone https://github.com/drshariqalikhan/oracle_chat.git
    cd oracle_chat
    cp .env.example .env
    nano .env

Set your preferred defaults in `.env` (for example `OPENROUTER_API_KEY=...` or `LLM_PROVIDER=ollama` + `MODEL_NAME=gemma3:4b`).

## 3. Run the Automated Setup Script

    bash deploy/oracle_setup.sh

To also pull `gemma3:4b` during setup:

    PULL_MODELS=true bash deploy/oracle_setup.sh

## 4. Verify Production Deployment
1. Check systemd services:

    sudo systemctl status oracle-chat
    sudo systemctl status ollama

2. Test endpoints on the VM:

    curl -s http://localhost:8080/health
    curl -s http://localhost:8080/api/providers
    curl -s http://localhost:8080/api/ollama/health

3. Open in your browser:

    http://<YOUR_ORACLE_PUBLIC_IP>:8080

## 5. Updating After Future GitHub Pushes

    cd ~/oracle_chat
    git pull origin main
    source venv/bin/activate
    pip install -r requirements.txt
    sudo systemctl restart oracle-chat
