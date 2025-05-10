from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel
import random
import uvicorn
import signal
import sys

app = FastAPI()
app.add_middleware(GZipMiddleware)

app.mount("/baker/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class Oven(BaseModel):
    id: int
    status: str  # "ON" or "OFF"
    temperature: int | None = None

ovens = {
    i: Oven(id=i, status=random.choice(["ON", "OFF"]), temperature=random.randint(150, 250))
    for i in range(1, 7)
}

@app.get("/baker", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "ovens": ovens.values()})

@app.get("/baker/api")
async def get_all_ovens():
    return list(ovens.values())

@app.get("/baker/api/{oven_id}")
async def get_oven(oven_id: int):
    if oven_id in ovens:
        return ovens[oven_id]
    return Response(status_code=404)

@app.post("/baker/api")
async def create_oven(oven: Oven):
    ovens[oven.id] = oven
    return oven

@app.put("/baker/api/{oven_id}")
async def update_oven(oven_id: int, updated: Oven):
    ovens[oven_id] = updated
    return updated

@app.delete("/baker/api/{oven_id}")
async def delete_oven(oven_id: int):
    if oven_id in ovens:
        del ovens[oven_id]
        return Response(status_code=204)
    return Response(status_code=404)

def graceful_shutdown(*args):
    print("Shutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
