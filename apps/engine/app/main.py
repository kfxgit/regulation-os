from fastapi import FastAPI

app = FastAPI(title="Regulation OS Engine")


@app.get("/health")
def health():
    return {"status": "ok", "service": "engine"}
