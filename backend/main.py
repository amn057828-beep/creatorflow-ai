from fastapi import FastAPI

app = FastAPI(
    title="CreatorFlow AI API",
    version="1.0.0"
)

@app.get("/")
def root():
    return {
        "status": "running",
        "app": "CreatorFlow AI"
    }

@app.get("/health")
def health():
    return {
        "status": "ok"
    }