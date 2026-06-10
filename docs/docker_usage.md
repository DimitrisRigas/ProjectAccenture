# Docker Usage

## Purpose

Docker is used to run the local application layer of the AI-Powered Regulatory Compliance Assistant.

The container runs:

- FastAPI backend
- RAG service
- API key authentication
- PII redaction
- Azure OpenAI client
- Azure AI Search client

Databricks, Azure OpenAI, and Azure AI Search remain external cloud services.

## Files

```text
Dockerfile
docker-compose.yml
.dockerignore

Build and Run:
docker compose up --build
API URL:
http://127.0.0.1:8000
Stop
docker compose down