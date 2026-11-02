"""
FastAPI demo for the Meta Media Buying Agent.

Run (after installing requirements):
    uvicorn app:app --reload

Try:
    GET  /report
    POST /approve  {"id": "...", "approved_by": "Client", "budget_change_pct": 20}
    POST /stop

This file is optional for the portfolio demo. The core logic lives in
agent.py and works with plain Python, no server needed. No live Meta
change is made by any endpoint in this demo.
"""

import csv
from pathlib import Path

from agent import ACTION_LOG, approve, daily_report, stop_agent

try:
    from fastapi import FastAPI
    from pydantic import BaseModel
except ImportError:  # pragma: no cover
    FastAPI = None
    BaseModel = object


if FastAPI is None:
    raise SystemExit("Install requirements first: pip install -r requirements.txt")

app = FastAPI(title="Meta Media Buying Agent (Demo)")

DATA_FILE = Path(__file__).parent / "campaigns_sample.csv"


def _load():
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Approval(BaseModel):
    id: str
    approved_by: str = ""
    budget_change_pct: float = 0.0


@app.get("/health")
def health():
    return {"status": "ok", "mode": "demo - no live Meta changes"}


@app.get("/report")
def report():
    return daily_report(_load())


@app.post("/approve")
def approve_endpoint(body: Approval):
    recs = {r["id"]: r for r in daily_report(_load())["recommendations"]}
    rec = recs.get(body.id)
    if rec is None:
        return {"result": "NOT_FOUND", "id": body.id}
    return approve(rec, approved_by=body.approved_by,
                   budget_change_pct=body.budget_change_pct)


@app.post("/stop")
def stop():
    return stop_agent()


@app.get("/log")
def log():
    return {"action_log": ACTION_LOG}
