from fastapi import FastAPI

from app.routes import embed, health, ingest, memories, process, remember, search


app = FastAPI(title="Cortex Engine")

app.include_router(health.router)
app.include_router(remember.router)
app.include_router(process.router)
app.include_router(embed.router)
app.include_router(search.router)
app.include_router(ingest.router)
app.include_router(memories.router)


@app.get("/")
def root():
    return {
        "name": "Cortex Engine",
        "status": "awake",
    }
