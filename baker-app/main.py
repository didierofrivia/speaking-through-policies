from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
import random

app = FastAPI()
app.mount("/baker/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class Oven(BaseModel):
    id: int
    status: str  # "ON" or "OFF"
    temperature: Optional[int] = None

ovens = {}

def init_ovens():
    global ovens
    ovens = {
        i: Oven(
            id=i,
            status=random.choice(["ON", "OFF"]),
            temperature=random.randint(150, 300) if random.random() > 0.4 else None
        )
        for i in range(1, 7)
    }

init_ovens()

@app.get("/baker/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "ovens": list(ovens.values())})

@app.get("/baker/api")
def get_ovens():
    return list(ovens.values())

@app.get("/baker/api/{oven_id}")
def get_oven(oven_id: int):
    oven = ovens.get(oven_id)
    if not oven:
        raise HTTPException(status_code=404, detail="Oven not found")
    return oven

@app.post("/baker/api", status_code=201)
def create_oven(oven: Oven):
    if oven.id in ovens:
        raise HTTPException(status_code=400, detail="Oven already exists")
    ovens[oven.id] = oven
    return oven

@app.put("/baker/api/{oven_id}")
def update_oven(oven_id: int, oven_data: Oven):
    if oven_id not in ovens:
        raise HTTPException(status_code=404, detail="Oven not found")
    ovens[oven_id] = oven_data
    return oven_data

@app.delete("/baker/api/{oven_id}", status_code=204)
def delete_oven(oven_id: int):
    if oven_id not in ovens:
        raise HTTPException(status_code=404, detail="Oven not found")
    del ovens[oven_id]
