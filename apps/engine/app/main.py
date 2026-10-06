from fastapi import FastAPI

from app.api.impact import router as impact_router
from app.api.search import router as search_router

app = FastAPI(title="Regulation OS Engine")
app.include_router(search_router)
app.include_router(impact_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "engine"}
