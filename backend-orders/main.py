from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import crud, schemas, database
from events import router as events_router

app = FastAPI(title="Drone Delivery Orders Service")

# allow your three frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# include websocket router
app.include_router(events_router)

# startup/shutdown
@app.on_event("startup")
async def startup():
    await database.database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.database.disconnect()

# ------------------- REST API -------------------
@app.post("/api/orders", response_model=schemas.Order)
async def create_order(order: schemas.OrderCreate):
    return await crud.create_order(order)

@app.get("/api/orders", response_model=List[schemas.Order])
async def list_orders():
    return await crud.get_orders()

@app.get("/api/orders/{order_id}", response_model=schemas.Order)
async def get_order(order_id: str):
    return await crud.get_order(order_id)

@app.patch("/api/orders/{order_id}", response_model=schemas.Order)
async def update_order(order_id: str, payload: schemas.OrderUpdate):
    return await crud.update_order(order_id, payload)
