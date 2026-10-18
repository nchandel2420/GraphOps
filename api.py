from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent import build_agent, ask_agent

app = FastAPI(title="GraphOps API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Build the agent once when the API starts.
agent = build_agent()


class InvestigationRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "GraphOps API"}


@app.post("/api/investigate")
def investigate(request: InvestigationRequest):
    try:
        answer = ask_agent(agent, request.question)

        return {
            "question": request.question,
            "answer": answer,
        }

    except Exception as exc:
        print(f"[ERROR] GraphOps investigation failed: {exc}")
        raise HTTPException(
            status_code=500,
            detail="The investigation failed. Check the backend logs.",
        ) from exc
