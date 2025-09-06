import time
import threading
import asyncio
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import collections
import collections.abc
import os
# Compatibility shim for Python 3.10+: MutableMapping/MutableSet/Mapping moved to collections.abc
if not hasattr(collections, "MutableMapping"):
    collections.MutableMapping = collections.abc.MutableMapping
if not hasattr(collections, "MutableSet"):
    collections.MutableSet = collections.abc.MutableSet
if not hasattr(collections, "Mapping"):
    collections.Mapping = collections.abc.Mapping
from dronekit import connect, VehicleMode, LocationGlobalRelative
from pymavlink import mavutil
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import json

# Configuration
BLOCK_COORDINATES = {
    "A": {"lat": 16.462584016312782, "lon": 80.50752136420085},
    "B": {"lat": 16.460755182984183, "lon": 80.50745167996868},
    "C": {"lat": 16.464311965140684, "lon": 80.50803103711354},
}

HOME_LOCATION = {"lat": 16.463000, "lon": 80.507800}

# Mission speed configuration (EASY TO TUNE)
# Horizontal cruise speed used with simple_goto for Copter (m/s)
MISSION_GROUNDSPEED_MPS = 5.0

# Optionally set ArduCopter WPNAV speeds (applies vehicle-wide). Disable if you don't want to modify parameters.
SET_WPNAV_PARAMS = True
WPNAV_SPEED_MPS = 5.0        # horizontal speed (m/s)
WPNAV_SPEED_UP_MPS = 2.0     # climb speed (m/s)
WPNAV_SPEED_DN_MPS = 1.5     # descent speed (m/s)

# Store drone connections by droneId
DRONES: Dict[str, 'DroneDelivery'] = {}
DRONE_LOCK = threading.Lock()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Mark for removal
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

manager = ConnectionManager()

# Database setup
engine = create_engine('sqlite:///drone_orders.db')
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True, index=True)
    drone_id = Column(String, index=True)
    block = Column(String)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

Base.metadata.create_all(bind=engine)

# Pydantic Models
class LaunchRequest(BaseModel):
    droneId: str
    connectionString: str
    block: str
    orderId: Optional[str] = None  # ID from orders service to sync status updates

class StatusRequest(BaseModel):
    droneId: str

class DroneStatus(BaseModel):
    armed: bool
    mode: str
    altitude: float
    connection_string: str
    battery: Optional[float] = None
    location: Optional[Dict[str, float]] = None

class MissionResponse(BaseModel):
    status: str
    order_id: int

class DroneDelivery:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.vehicle = connect(connection_string, wait_ready=True)
        self.lock = threading.Lock()
        self.is_connected = True
        # Will be set at mission start from current location
        self._home_location = None  # type: Optional[LocationGlobalRelative]
        # Optionally standardize WPNAV speeds for consistent behavior
        if SET_WPNAV_PARAMS:
            try:
                print("Setting WPNAV speed parameters for consistent groundspeed...")
                self.vehicle.parameters['WPNAV_SPEED'] = int(WPNAV_SPEED_MPS * 100)      # cm/s
                self.vehicle.parameters['WPNAV_SPEED_UP'] = int(WPNAV_SPEED_UP_MPS * 100)
                self.vehicle.parameters['WPNAV_SPEED_DN'] = int(WPNAV_SPEED_DN_MPS * 100)
                print("WPNAV parameters set.")
            except Exception as e:
                print(f"Warning: Failed to set WPNAV parameters: {e}")

    def arm_and_takeoff(self, target_altitude: float):
        with self.lock:
            print("Arming motors...")
            self.vehicle.mode = VehicleMode("GUIDED")
            self.vehicle.armed = True
            # Lock home location to prevent changes during the mission
            try:
                print("Locking home location to prevent changes...")
                self.vehicle.send_mavlink(self.vehicle.message_factory.command_long_encode(
                    0, 0,    # target_system, target_component
                    mavutil.mavlink.MAV_CMD_DO_SET_HOME,
                    0,       # confirmation
                    0,       # use current location
                    0, 0, 0, 0, 0, 0
                ))
                self.vehicle.flush()
                print("Home position locked!")
            except Exception as e:
                print(f"Warning: failed to lock home location: {e}")
            while not self.vehicle.armed:
                print("Waiting for arming...")
                time.sleep(1)
            print("Taking off...")
            self.vehicle.simple_takeoff(target_altitude)
            while True:
                print(f"Altitude: {self.vehicle.location.global_relative_frame.alt}")
                if self.vehicle.location.global_relative_frame.alt >= target_altitude * 0.95:
                    print("Target altitude reached!")
                    break
                time.sleep(1)

    def goto_location(self, lat: float, lon: float, cruise_alt: float = 20, final_alt: float = 1, notify_callback=None, delivered_callback=None):
        with self.lock:
            # Save current home before leaving
            print("Saving home location...")
            self._home_location = self.vehicle.location.global_relative_frame
            print(f"Home saved: Lat={self._home_location.lat}, Lon={self._home_location.lon}")

            # Fly to destination
            print(f"Flying to destination: Lat={lat}, Lon={lon}, Alt={cruise_alt}")
            target_location = LocationGlobalRelative(lat, lon, cruise_alt)
            # Use groundspeed for Copter to ensure consistent speed
            try:
                self.vehicle.simple_goto(target_location, groundspeed=MISSION_GROUNDSPEED_MPS)
            except TypeError:
                # Fallback if DroneKit version doesn't support groundspeed kwarg
                print("simple_goto groundspeed kwarg not supported; using default WPNAV speeds.")
                self.vehicle.simple_goto(target_location)

            # Wait until drone reaches the target location (simple geographic proximity)
            while True:
                current_lat = self.vehicle.location.global_relative_frame.lat
                current_lon = self.vehicle.location.global_relative_frame.lon
                distance = ((current_lat - lat)**2 + (current_lon - lon)**2) ** 0.5
                print(f"Current Location: Lat={current_lat}, Lon={current_lon}, Distance={distance}")
                if distance < 0.00005:
                    print("Destination reached!")
                    if notify_callback:
                        try:
                            notify_callback()
                        except Exception as e:
                            print(f"notify_callback error: {e}")
                    break
                time.sleep(1)

            # Descend to landing altitude
            print(f"Descending to {final_alt}m for landing...")
            self.vehicle.simple_goto(LocationGlobalRelative(lat, lon, final_alt))
            while self.vehicle.location.global_relative_frame.alt > final_alt * 1.1:
                print(f"Altitude: {self.vehicle.location.global_relative_frame.alt}")
                time.sleep(1)

            # Drop the payload via servo while still armed at low altitude for reliable actuation
            payload_dropped = False
            try:
                print("Dropping payload via servo...")
                self.set_servo(10, 1500)
                time.sleep(2)
                self.set_servo(10, 1000)
                payload_dropped = True
            except Exception as e:
                print(f"Warning: servo actuation failed: {e}")

            # Land and disarm; only consider delivery complete after disarm + payload_dropped
            print("Landing...")
            self.vehicle.mode = VehicleMode("LAND")
            while self.vehicle.armed:
                print("Waiting for disarm after landing...")
                time.sleep(1)
            print("Landed and disarmed.")

            if delivered_callback and payload_dropped:
                try:
                    delivered_callback()
                except Exception as e:
                    print(f"delivered_callback error: {e}")

            # Re-arm and take off again for return flight
            print("Re-arming for return flight...")
            self.vehicle.mode = VehicleMode("GUIDED")
            self.vehicle.armed = True
            while not self.vehicle.armed:
                print("Waiting for re-arming...")
                time.sleep(1)

            print("Taking off for return flight...")
            self.vehicle.simple_takeoff(cruise_alt)
            while self.vehicle.location.global_relative_frame.alt < cruise_alt * 0.95:
                print(f"Altitude: {self.vehicle.location.global_relative_frame.alt}")
                time.sleep(1)
            print("Reached cruise altitude.")

            # Return to saved home location
            if self._home_location is None:
                print("Warning: home location not set, using current as home.")
                self._home_location = self.vehicle.location.global_relative_frame
            print(f"Returning to saved home point: Lat={self._home_location.lat}, Lon={self._home_location.lon}")
            try:
                self.vehicle.simple_goto(LocationGlobalRelative(self._home_location.lat, self._home_location.lon, cruise_alt),
                                         groundspeed=MISSION_GROUNDSPEED_MPS)
            except TypeError:
                self.vehicle.simple_goto(LocationGlobalRelative(self._home_location.lat, self._home_location.lon, cruise_alt))

            while True:
                current_lat = self.vehicle.location.global_relative_frame.lat
                current_lon = self.vehicle.location.global_relative_frame.lon
                distance = ((current_lat - self._home_location.lat)**2 + (current_lon - self._home_location.lon)**2) ** 0.5
                print(f"Current Location: Lat={current_lat}, Lon={current_lon}, Distance={distance}")
                if distance < 0.00005:
                    print("Returned to home!")
                    break
                time.sleep(1)

            print("Stabilizing before landing at home...")
            time.sleep(2)
            print("Landing at home location...")
            self.vehicle.mode = VehicleMode("LAND")

            while self.vehicle.armed:
                print("Waiting for disarm after landing...")
                time.sleep(1)

            print("Mission complete. Landed and disarmed at home.")

    def goto_home(self):
        with self.lock:
            # Prefer saved home; fallback to constant
            if self._home_location is None:
                lat, lon = HOME_LOCATION["lat"], HOME_LOCATION["lon"]
            else:
                lat, lon = self._home_location.lat, self._home_location.lon
            print(f"Returning to home: Lat={lat}, Lon={lon}")
            try:
                self.vehicle.simple_goto(LocationGlobalRelative(lat, lon, 10), groundspeed=MISSION_GROUNDSPEED_MPS)
            except TypeError:
                self.vehicle.simple_goto(LocationGlobalRelative(lat, lon, 10))
            while True:
                current_lat = self.vehicle.location.global_relative_frame.lat
                current_lon = self.vehicle.location.global_relative_frame.lon
                distance = ((current_lat - lat)**2 + (current_lon - lon)**2) ** 0.5
                print(f"Current Location: Lat={current_lat}, Lon={current_lon}, Distance={distance}")
                if distance < 0.0001:
                    print("Home reached!")
                    break
                time.sleep(1)
            print("Landing at home...")
            self.vehicle.mode = VehicleMode("LAND")
            while self.vehicle.armed:
                print("Waiting for landing at home...")
                time.sleep(1)

    def set_servo(self, channel: int, pwm_value: int):
        print(f"Setting servo at channel {channel} to PWM {pwm_value}")
        self.vehicle.send_mavlink(self.vehicle.message_factory.command_long_encode(
            0, 0,
            mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
            0,
            channel,
            pwm_value,
            0, 0, 0, 0, 0
        ))
        self.vehicle.flush()

    def get_status(self) -> DroneStatus:
        try:
            location = self.vehicle.location.global_relative_frame
            return DroneStatus(
                armed=self.vehicle.armed,
                mode=self.vehicle.mode.name,
                altitude=location.alt,
                connection_string=self.connection_string,
                battery=getattr(getattr(self.vehicle, 'battery', None), 'level', None),
                location={
                    "lat": location.lat,
                    "lon": location.lon,
                    "alt": location.alt
                }
            )
        except Exception as e:
            print(f"Error getting drone status: {e}")
            return DroneStatus(
                armed=False,
                mode="UNKNOWN",
                altitude=0.0,
                connection_string=self.connection_string,
                battery=None,
                location=None
            )

    def close_connection(self):
        print("Closing connection...")
        self.is_connected = False
        self.vehicle.close()

    def perform_delivery(self, block_coords, home_coords, notify_callback=None, delivered_callback=None):
        try:
            # 1) Arm and takeoff to cruise altitude
            self.arm_and_takeoff(20)
            # 2) Full delivery mission: fly to block, land/disarm, servo drop, rearm, and return to saved home
            self.goto_location(block_coords["lat"], block_coords["lon"], cruise_alt=20, final_alt=1, notify_callback=notify_callback, delivered_callback=delivered_callback)
        except Exception as e:
            print(f"Error in delivery: {e}")

# FastAPI App
app = FastAPI(
    title="Drone Delivery API",
    description="Real-time drone delivery system for college campus",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "Drone Delivery API",
        "version": "1.0.0",
        "endpoints": {
            "launch": "POST /api/launch",
            "status": "POST /api/status",
            "websocket": "WS /ws",
            "docs": "GET /docs"
        }
    }

@app.post("/api/launch", response_model=MissionResponse)
async def launch_mission(request: LaunchRequest):
    """Launch a drone mission to a specific block"""
    if request.block not in BLOCK_COORDINATES:
        raise HTTPException(status_code=400, detail="Invalid block. Must be A, B, or C")
    
    with DRONE_LOCK:
        if request.droneId not in DRONES:
            try:
                DRONES[request.droneId] = DroneDelivery(request.connectionString)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to connect to drone: {str(e)}")
        drone = DRONES[request.droneId]
    
    coords = BLOCK_COORDINATES[request.block]
    session = SessionLocal()
    order = Order(drone_id=request.droneId, block=request.block, status='IN_PROGRESS')
    session.add(order)
    session.commit()
    order_id = order.id

    def notify_user():
        asyncio.run(manager.broadcast(json.dumps({
            "type": "arrived_at_block",
            "drone_id": request.droneId,
            "order_id": order_id,
            "block": request.block
        })))

    def mission():
        try:
            def mark_delivered():
                # Update local order status in this service (debug/info)
                try:
                    session = SessionLocal()
                    o = session.query(Order).get(order_id)
                    if o:
                        o.status = 'DELIVERED'
                        o.completed_at = datetime.datetime.utcnow()
                        session.commit()
                    session.close()
                except Exception as e:
                    print(f"Warning: failed to update local order record: {e}")

                # Also notify the Orders Service (port 8001) if request.orderId is provided
                if request.orderId:
                    try:
                        ORDERS_API_BASE = os.getenv("ORDERS_API_BASE", "http://127.0.0.1:8001")
                        resp = requests.patch(
                            f"{ORDERS_API_BASE}/api/orders/{request.orderId}",
                            json={"status": "Delivered"},
                            timeout=5,
                        )
                        if not resp.ok:
                            print(f"Orders service update failed: {resp.status_code} {resp.text}")
                        else:
                            print(f"Orders service updated: order {request.orderId} -> Delivered")
                    except Exception as e:
                        print(f"Orders service update error: {e}")

                # Broadcast to any listeners on this service
                asyncio.run(manager.broadcast(json.dumps({
                    "type": "order_delivered",
                    "drone_id": request.droneId,
                    "order_id": request.orderId or order_id,
                })))

            drone.perform_delivery(coords, HOME_LOCATION, notify_callback=notify_user, delivered_callback=mark_delivered)
            session = SessionLocal()
            order = session.query(Order).get(order_id)
            order.status = 'COMPLETED'
            order.completed_at = datetime.datetime.utcnow()
            session.commit()
            session.close()
            asyncio.run(manager.broadcast(json.dumps({
                "type": "mission_completed",
                "drone_id": request.droneId,
                "order_id": order_id,
                "block": request.block
            })))
        except Exception as e:
            session = SessionLocal()
            order = session.query(Order).get(order_id)
            order.status = f'FAILED: {str(e)}'
            session.commit()
            session.close()
            print(f"Mission error for {request.droneId}: {e}")
            asyncio.run(manager.broadcast(json.dumps({
                "type": "mission_failed",
                "drone_id": request.droneId,
                "order_id": order_id,
                "error": str(e)
            })))
    t = threading.Thread(target=mission)
    t.start()
    session.close()
    
    return MissionResponse(
        status=f"Mission started for drone {request.droneId}",
        order_id=order_id
    )

@app.post("/api/status", response_model=DroneStatus)
async def get_drone_status(request: StatusRequest):
    """Get the current status of a drone or connect to it"""
    # If drone is not in memory, try to connect to it
    if request.droneId not in DRONES:
        # For now, we'll create a mock connection since we can't connect without connection string
        # In a real scenario, you'd need to pass the connection string
        raise HTTPException(status_code=404, detail="Drone not connected. Please provide connection string.")
    
    drone = DRONES[request.droneId]
    return drone.get_status()

@app.post("/api/connect")
async def connect_drone(request: LaunchRequest):
    """Connect to a drone with the provided connection string"""
    if not request.connectionString or not isinstance(request.connectionString, str):
        raise HTTPException(status_code=400, detail="Invalid connection string.")
    try:
        with DRONE_LOCK:
            if request.droneId in DRONES:
                DRONES[request.droneId].close_connection()
            # Try connecting and catch errors
            try:
                drone = DroneDelivery(request.connectionString)
            except Exception as e:
                print(f"[ERROR] Failed to connect to drone {request.droneId}: {e}")
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"Failed to connect to drone: {str(e)}")
            DRONES[request.droneId] = drone
        return {"status": f"Successfully connected to drone {request.droneId}", "drone_id": request.droneId}
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time drone updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Send periodic status updates for all connected drones
            status_updates = {}
            with DRONE_LOCK:
                for drone_id, drone in DRONES.items():
                    if drone.is_connected:
                        status_updates[drone_id] = drone.get_status().dict()
            
            await websocket.send_text(json.dumps({
                "type": "status_update",
                "drones": status_updates,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }))
            
            await asyncio.sleep(2)  # Update every 2 seconds
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/drones")
async def list_drones():
    """List all connected drones"""
    with DRONE_LOCK:
        return {
            "connected_drones": list(DRONES.keys()),
            "total_count": len(DRONES)
        }

@app.delete("/api/drones/{drone_id}")
async def disconnect_drone(drone_id: str):
    """Disconnect a specific drone"""
    with DRONE_LOCK:
        if drone_id in DRONES:
            DRONES[drone_id].close_connection()
            del DRONES[drone_id]
            return {"message": f"Drone {drone_id} disconnected"}
        else:
            raise HTTPException(status_code=404, detail="Drone not found")

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Drone Delivery Backend with FastAPI...")
    print("📡 API Endpoints:")
    print("   POST /api/launch - Start drone mission")
    print("   POST /api/status - Get drone status")
    print("   GET  /api/drones - List connected drones")
    print("   WS   /ws - Real-time WebSocket updates")
    print("   GET  /docs - Interactive API documentation")

    host = os.getenv("HOST", "127.0.0.1")
    try:
        port = int(os.getenv("PORT", "8080"))
    except ValueError:
        port = 8080
    print(f"🌐 Server running on http://{host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    
    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    except Exception as e:
        print(f"Error starting server: {e}")
        import traceback
        traceback.print_exc()

# NOTE: Removed stray React/JSX snippet that was accidentally appended here.