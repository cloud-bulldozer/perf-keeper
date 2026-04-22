"""REST API server for the perfscale diagnosis agent."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, HttpUrl

from perfscale_agent.agent import create_agent
from perfscale_agent.cli import _last_diagnosis_text

logger = logging.getLogger(__name__)

_agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent
    load_dotenv()
    _agent = await create_agent()
    yield


app = FastAPI(title="Perfscale Diagnosis Agent", lifespan=lifespan)


class AnalyzeRequest(BaseModel):
    job_url: HttpUrl


class AnalyzeResponse(BaseModel):
    passed: bool
    analysis: str


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    logger.info("Received analysis request for %s", req.job_url)
    state = await _agent.ainvoke({"job_url": str(req.job_url)})
    passed = state["passed"]
    if passed:
        return AnalyzeResponse(result=True, analysis="Job passed. No diagnosis required.")
    final = (state.get("final_report") or "").strip()
    if not final:
        messages = state.get("messages") or []
        final = _last_diagnosis_text(messages) or "No analysis produced."
    return AnalyzeResponse(result=False, analysis=final)
