<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/drive/1R8panwVoT7cDxmyhMLL__Qg_hDE0Au2G

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`

## Drone Backend (FastAPI) — Docker Compose

This repo also contains a FastAPI-based drone backend under `backend/` with a `Dockerfile` and a root-level `docker-compose.yml`.

### Prerequisites
- Docker Engine with compose-plugin (Docker Compose v2)
- Linux recommended (compose uses `network_mode: "host"`)

### Build and Run (Linux)
```bash
docker compose build backend
docker compose up -d backend
docker compose logs -f backend
```

The API will be available at: http://localhost:8080 (docs at `/docs`).

`docker-compose.yml` is configured to:
- Use host networking (ideal for MAVLink UDP and local tooling)
- Set `CORS_ORIGINS=*` (adjust for production)
- Send delivery status updates to your deployed Orders API at `https://areodrone-database.onrender.com` via `ORDERS_API_BASE`.

### Windows (Docker Desktop)
Docker Desktop on Windows does not support `network_mode: "host"`. Use the provided override file `docker-compose.windows.yml`, which maps TCP 8080 and UDP 14550.

Ensure the SQLite DB file exists (recommended on Windows to avoid bind-mount quirks):
```powershell
New-Item -Path .\backend\drone_orders.db -ItemType File -Force | Out-Null
```

Build, run, and view logs:
```powershell
docker compose -f docker-compose.yml -f docker-compose.windows.yml build backend
docker compose -f docker-compose.yml -f docker-compose.windows.yml up -d backend
docker compose -f docker-compose.yml -f docker-compose.windows.yml logs -f backend
```

Verify the API:
- Open http://localhost:8080/docs

MAVLink UDP on Windows:
- Configure your simulator/GCS to send MAVLink to `127.0.0.1:14550`.
- In the Admin UI, use the connection string: `udp:0.0.0.0:14550`.
- Ensure Windows Firewall allows inbound UDP on port 14550 (and TCP 8080 if accessed from other devices).

### Frontend → Backend URLs
- Frontend Orders API base: set to `https://areodrone-database.onrender.com`
- Frontend Drone API base (local): `http://127.0.0.1:8080`

In the Vite frontend, set in `.env.*` files as needed:
```
VITE_API_BASE=https://areodrone-database.onrender.com
VITE_DRONE_API_BASE=http://127.0.0.1:8080
```

---

## Using ArduPilot SITL (Simulation)

You can simulate a drone using ArduPilot SITL on your Linux host. The common setup forwards MAVLink to UDP port 14550.

1. Start SITL (examples; pick your preferred method):
   - With `sim_vehicle.py` (from the ArduPilot repo tools):
     ```bash
     sim_vehicle.py -v ArduCopter --map --console
     ```
     This typically emits MAVLink on UDP 14550 to localhost.
   - Or using MAVProxy to forward explicitly:
     ```bash
     mavproxy.py --master tcp:127.0.0.1:5760 --out udp:127.0.0.1:14550
     ```

2. Ensure the backend container is running with host networking (as provided here). No UDP port mapping is required with `network_mode: host`.

3. From the Admin UI (frontend), connect using this connection string:
   - `127.0.0.1:14550`

4. Launch a mission from the UI. The backend will connect via DroneKit and update the Orders service upon delivery.

Notes:
- If something else is already bound to UDP/14550, free it or change to another port consistently in SITL and in the UI connection string.

---

## Connect via Hardware UDP (no USB)

If your flight controller or ground station forwards MAVLink over UDP (Wi‑Fi/Ethernet) to your laptop:

1. Configure the autopilot/GCS to send MAVLink to your laptop’s IP on UDP port 14550 (e.g., `192.168.1.10:14550`).
2. Keep the backend running with host networking (`docker-compose.yml` already does this).
3. From the Admin UI, use a connection string that listens on port 14550 on the host:
   - Preferred: `127.0.0.1:14550`
   - Alternative (bind all interfaces): `0.0.0.0:14550`

Tips:
- Make sure your system firewall allows inbound UDP 14550 on the host.
- Avoid running multiple listeners on the same UDP port.

---

## Optional: Connect over USB (Pixhawk/Telemetry)

If you later connect via USB serial, uncomment the device mapping in `docker-compose.yml`:

```yaml
# If connecting via USB to Pixhawk/Telemetry, uncomment:
# devices:
#   - "/dev/ttyUSB0:/dev/ttyUSB0"   # or /dev/ttyACM0
# group_add:
#   - "dialout"
```

And use a serial connection string in the Admin UI:
- `serial:/dev/ttyUSB0:57600`  (or `serial:/dev/ttyACM0:57600`)

Host setup for USB:
- Add your user to the `dialout` group: `sudo usermod -a -G dialout $USER` then `newgrp dialout` (or re-login)
- Verify the device path with: `ls -l /dev/ttyUSB* /dev/ttyACM*` or `ls -l /dev/serial/by-id/`

---

## Troubleshooting

- Docker permission error (cannot access `/var/run/docker.sock`):
  - Ensure Docker is running: `sudo systemctl status docker`
  - Add your user to docker group: `sudo usermod -aG docker $USER && newgrp docker`

- Healthcheck failing:
  - Check logs: `docker compose logs -f backend`
  - Confirm API is reachable: http://localhost:8080/docs

- CORS issues:
  - `backend/main.py` reads `CORS_ORIGINS` from env. In compose it defaults to `*`. Restrict it in production to your frontend origin.

- Orders API updates:
  - `ORDERS_API_BASE` in compose points to `https://areodrone-database.onrender.com`. If you change deployments, update this value.

---

## Step 10 — Nginx Reverse Proxy + TLS (Let's Encrypt)

Expose the backend securely on a public domain using Nginx as a reverse proxy. This supports WebSockets and HTTPS.

### 1) Install Nginx and Certbot (Ubuntu)
```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 2) Place the site configuration
- Copy the example site file from this repo:
  - `deploy/nginx/drone.conf` → `/etc/nginx/sites-available/drone.conf`
- Edit `server_name` to your domain (e.g., `api.yourdomain.com`).

### 3) Enable the site and reload Nginx
```bash
sudo ln -s /etc/nginx/sites-available/drone.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

If using UFW firewall:
```bash
sudo ufw allow 'Nginx Full'
```

### 4) Ensure the backend is listening on localhost:8080
This repo’s `docker-compose.yml` runs the backend on host network and binds to `127.0.0.1:8080`. Verify:
```bash
curl -I http://127.0.0.1:8080/
```

### 5) Obtain a TLS certificate (Let's Encrypt)
```bash
sudo certbot --nginx -d api.yourdomain.com
```
Choose the redirect-to-HTTPS option. Certbot will update Nginx automatically.

### 6) Frontend configuration (Vite)
Point the frontend to your HTTPS API domain:
```
VITE_DRONE_API_BASE=https://api.yourdomain.com
```
The WebSocket URL will automatically use `wss://` in the app code.

### 7) Verification
- Open `https://api.yourdomain.com/docs`
- DevTools Network → confirm HTTPS + `wss://api.yourdomain.com/ws` upgrades successfully

### Notes
- The Nginx example already includes WebSocket headers (`Upgrade` and `Connection`).
- Keep `network_mode: "host"` for the backend container to simplify UDP/serial access.
- If you change the backend port, update `proxy_pass` in Nginx accordingly.
