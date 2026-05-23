from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agent import run_agent

app = FastAPI(title="Claude Agent")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")
    result = run_agent(req.message)
    return ChatResponse(response=result)


@app.get("/health")
def health():
    return {"status": "ok"}
