# NetMoniAI

**NetMoniAI** is a network‑monitoring AI system with a FastAPI backend (REST + optional WebSocket) and a React frontend for real‑time visualization. It includes agent modules for security analysis, performance monitoring, reporting, and parameter tuning, plus demo JSONs to preview the UI.

![Architecture](Architecture.jpeg)

---

## ✨ Features
- **Multi‑agent backend**: `SecurityAnalysisAgent`, `PerformanceMonitoringAgent`, `ReportingAgent`, `ParameterTuningAgent`, `ChatAgent`
- **Traffic analytics utilities**: PCAP parsing and attack detection (`backend/tools/*`)
- **Real‑time UI**: React dashboards (`GlobalControllerDashboard`, `LocalControllerDashboard`) and a `NetworkVisualizer`
- **Demo datasets**: `nodes_data.json` + `packets_data.json` (8‑node and 20‑node scenarios)
- **Simulation XMLs**: example DoS/SYN flood scenarios to drive animations

---

## 📁 Repository Structure (high level)

```
backend/
  app.py                 # FastAPI app (REST)
  appWebsocket.py        # WebSocket server (if run separately)
  config.py              # Backend config (envs, ports, etc.)
  utils.py, common_classes.py
  nw_agents/             # Agent implementations
  tools/                 # PCAP + attack detection utilities
  *.xml                  # Simulation/animation scenarios
  *.log                  # Logs (runtime & metrics)
  requirements.txt

frontend/
  public/                # Static assets + default nodes/packets JSON
  src/                   # React app (components, API service, styles)
  package.json
  README.md              # Frontend-specific notes (if any)

requirements.txt         # (root if used)
Architecture.jpeg
.gitignore
```

---

## 🚀 Quick Start (Developer Setup)

### Prerequisites
- **Python** 3.10+
- **Node.js** 18+ and **npm** 9+
- **Git**

> If you later see CORS or connection issues, it’s usually a URL/port mismatch between the frontend and backend.

### 1) Backend (FastAPI)

```bash
# from repo root
cd backend

# create & activate a virtualenv
# Windows (PowerShell)
python -m venv .venv
. .venv/Scripts/Activate.ps1

# macOS/Linux
# python3 -m venv .venv
# source .venv/bin/activate

# install deps
pip install -r requirements.txt
```

Create a `.env` (optional, recommended). Open `backend/config.py` to see recognized variables (ports, log level, API keys). Example:

```bash
# backend/.env (example)
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
# If you use any LLM/API keys, define them here too
# OPENAI_API_KEY=...
```

Run the REST API (option A):

```bash
# from repo root so module imports resolve
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

Run a separate WebSocket server (option B, only if your design splits them):

```bash
# check appWebsocket.py for the actual port/path used
python backend/appWebsocket.py
```

> If your WebSocket is integrated into the same FastAPI app, you only need the first command.

---

### 2) Frontend (React)

```bash
# in a new terminal, from repo root
cd frontend
npm install
```

Configure environment for API/WS URLs (either via `.env` or update `src/apiService.js`):

```bash
# frontend/.env (example)
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8001
```

Start the dev server:

```bash
npm start
```

Open **http://localhost:3000** in your browser.

---

## 🧪 Demo Mode (no backend required)

To quickly showcase the UI without running live analysis, the frontend can read bundled JSONs from `frontend/public/`:

- `nodes_data.json`
- `packets_data.json`

There are additional demo files under:
- `frontend/jsons/nodes-8-nodes-1st/`
- `frontend/jsons/jsons-20-nodes/`

During development, you can fetch from `/nodes_data.json` and `/packets_data.json` (the public folder) when `REACT_APP_API_URL` is empty or when you add a simple toggle in the code.

---

## 🔌 API & WebSocket (adjust to your code)

Exact routes depend on your `backend/app.py` and `appWebsocket.py`. Common patterns include:

- Health: `GET /health`
- Analyze/ingest: `POST /analyze` (e.g., analyze PCAP/JSON data)
- WebSocket: `ws://<host>:<port>/ws` (stream metrics/events)

Check the files to confirm the actual endpoints/paths and update the frontend `apiService.js` accordingly.

---

## 📊 PCAP & Analytics Utilities

Utilities live in `backend/tools/`:

- `pcap_analyzer.py` — parsing/analyzing PCAPs
- `attack_detection*.py` — detection heuristics/logic
- `data_collection.py` — data prep / metrics extraction

Typical script usage (see the file’s `__main__` or comments):

```bash
python backend/tools/pcap_analyzer.py <path-to-pcap>
```

Simulation/animation XMLs (e.g., `syn-flood-animation.xml`, `dos-simulation-animation.xml`, `simulation3.xml`) can be used to generate synthetic flows for the UI.

---

## 🧠 Agents Overview

- **SecurityAnalysisAgent** — flags anomalies/attacks from flows or summaries
- **PerformanceMonitoringAgent** — tracks throughput, latency, drops; pushes alerts
- **ReportingAgent** — summarizes results and generates reports
- **ParameterTuningAgent** — adjusts thresholds or model parameters over time
- **ChatAgent** — natural‑language interface to metrics/history

Agent code is under `backend/nw_agents/`.

---

## 🗂 Logs & History

- `backend/agent_app.log`, `backend/network_metrics.log`, `backend/metrics_metrics.log`
- History snapshots: `backend/history.json`, `backend/history_backup.json`

These help with debugging and reviewing prior events.

---

## 🛠 Troubleshooting

- **CORS errors**: ensure `REACT_APP_API_URL` matches your backend host/port; enable CORS in FastAPI if needed.
- **WebSocket not connecting**: verify the WS port and path; align `REACT_APP_WS_URL` with `appWebsocket.py` (or the WS route in `app.py`).
- **Module import issues**: run servers from the **repo root** so `backend/` resolves as a package.
- **Windows PowerShell venv activation**: use `. .venv/Scripts/Activate.ps1`. If blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (then reopen PowerShell).

---

## 📦 Production Build

```bash
# frontend
npm run build
# serve the build with your preferred static server or reverse proxy (nginx, etc.)
```

Run backend with a production server (e.g., `uvicorn` behind `gunicorn`/`nginx`) and set proper environment variables.

---

## 🤝 Contributing

PRs and issues are welcome. Please:
1. Open an issue describing the change
2. Use feature branches
3. Keep commits scoped and descriptive

---

## 📄 License

Add your license of choice (e.g., MIT/Apache‑2.0) at the repo root as `LICENSE`.

---

## 📝 Git Tips

If your local branch shows a missing upstream:
```bash
git branch --unset-upstream                 # remove broken link
git remote add origin https://github.com/<USER>/<REPO>.git
git push -u origin main
```
