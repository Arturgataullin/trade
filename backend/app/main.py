from fastapi import FastAPI

app = FastAPI(title="Exchange Simulator")

@app.get("/health")
def health():
    return {"status": "ok"}