# GraphOps — Evidence-Based Incident Investigation

GraphOps is an AI-powered incident investigation assistant that uses a graph database to trace service dependencies, identify potentially affected projects, retrieve service ownership, and review historical incidents and decisions.

## Problem

During an incident, engineers need to understand which services depend on the failed component, which projects may be affected, who owns the relevant services, and whether similar incidents or decisions exist in the graph.

GraphOps brings this information together through natural-language queries backed by graph data.

## Technology Stack

- **Graph database:** FalkorDB
- **Agent orchestration:** LangGraph and LangChain
- **LLM integration:** Groq and/or OpenAI, depending on configuration
- **Backend:** Python and FastAPI
- **Frontend:** React and Vite
- **Configuration:** Environment variables with `python-dotenv`

## Key Features

- Resolve services by name or ID.
- Trace direct and indirect service dependencies.
- Identify projects potentially affected by a service failure.
- Distinguish direct project membership from indirect impact.
- Retrieve service ownership and historical incident information.
- Present evidence-backed investigation results.

## Architecture

1. The React frontend sends a user question to the FastAPI backend.
2. The agent selects graph tools to investigate the question.
3. Graph tools query FalkorDB for services, dependencies, projects, owners, incidents, and decisions.
4. The agent returns a response grounded in the retrieved graph data.

## Run Locally

### Prerequisites

- Python installed
- Node.js and npm installed
- Docker installed
- Access to an LLM API key supported by the project

### 1. Configure environment variables

Create a local `.env` file using the variable names expected by the application. Do not commit API keys or credentials.

### 2. Start FalkorDB

From the repository root:

```bash
docker compose up -d
```

### 3. Install Python dependencies

```bash
python -m venv .venv
```

Activate the virtual environment on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 4. Start the backend

Use the FastAPI application entry point and port configured in `api.py`.

### 5. Start the frontend

```bash
cd graphops-ui
npm install
npm run dev
```

Open the local URL printed by Vite.

> Verify the environment variables, database ports, and backend startup command against the actual project configuration before relying on these instructions.

## Example Investigation

Question: Which projects directly contain Payment Gateway (S3), and which may be indirectly affected?

GraphOps distinguishes direct project membership from indirect dependency paths. For example, a project containing a service that depends on Payment Service, which in turn depends on Payment Gateway, may be indirectly affected even when it does not directly contain Payment Gateway.

## Demo

Demo video: Add link before submission.

## Hackathon Submission

- **Project:** GraphOps
- **Repository:** https://github.com/nchandel2420/GraphOps
- **Track:** Select the track that best matches the submitted implementation.
- **AI assistance:** Disclose AI tools used according to the hackathon rules.

## Limitations

Graph-based dependency paths establish potential impact routes. They do not, by themselves, prove root cause or confirm that a downstream service has failed.