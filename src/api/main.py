"""Entry point for the Horison ESG Scoring Service."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.api.provenance import router as prov_router

app = FastAPI(
    title="Horison ESG Scoring API",
    description=(
        "Trustworthy, outcome-based, auditable ESG scoring for private markets. "
        "Every score is traceable to its source evidence. "
        "Designed for SFDR, CSRD and ISSB compliance."
    ),
    version="0.1.0",
    contact={"name": "Horison.ai", "email": "hello@horison.ai"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(prov_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "horison-esg"}
