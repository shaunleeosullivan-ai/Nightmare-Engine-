# CLAUDE.md — Nightmare Engine Codebase Guide

This file provides AI assistants with essential context for working on the Nightmare Engine codebase.

---

## Project Overview

**Nightmare Engine** is a bio-adaptive horror RPG platform that uses real-time biometric data (heart rate, facial emotion, skin conductance) to dynamically adjust horror narrative intensity. It is a full-stack web application:

- **Backend:** Python/FastAPI with WebSocket real-time communication
- **Frontend:** Single-file vanilla HTML/CSS/JavaScript (`index.html`)
- **AI Narrative:** Ollama LLM integration (`llama3.1:8b`) with predefined fallback fragments
- **Biometrics:** OpenCV rPPG heart-rate extraction + DeepFace emotion detection

---

## Repository Structure

```
Nightmare-Engine-/
├── main.py              # Entire backend — FastAPI app, WebSockets, biometric logic (~890 lines)
├── index.html           # Entire frontend — UI, WebSocket client, audio (~543 lines)
├── requirements.txt     # Python pip dependencies
├── README.md            # Minimal placeholder
├── CLAUDE.md            # This file
└── .github/
    └── workflows/
        └── python-package-conda.yml  # CI/CD (GitHub Actions)
```

The codebase is deliberately monolithic: one backend file, one frontend file.

---

## Running the Project

### Prerequisites

- Python 3.10+
- Ollama running locally with `llama3.1:8b` model (optional — fallback narratives exist)
- Webcam (optional — simulation mode available)

### Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** Some packages (TensorFlow, DeepFace, MediaPipe) are heavy. The server gracefully degrades if they fail to import.

### Start the Server

```bash
python main.py
```

The server starts on `http://localhost:8000` by default. Open `index.html` in a browser or navigate to `http://localhost:8000`.

---

## Key Architecture

### Bio-Adaptive Feedback Loop

```
Biometric Input (HR, GSR, Emotion)
  ↓
Session State Update (sessions[exp_id])
  ↓
Adaptive Intensity Calculation (0.0–1.0)
  ↓
LLM Narrative Generation (Ollama / fallback)
  ↓
WebSocket Broadcast → Frontend
```

### Session State (`sessions[exp_id]`)

All session state is held **in-memory** in the `sessions` dict. There is no database or Redis persistence — everything is lost on server restart.

Each session contains:
- `hr` — heart rate (bpm)
- `gsr` — skin conductance
- `emotion` — detected facial emotion string
- `intensity` — fear intensity float (0.0–1.0)
- `recursion_level` — meta-narrative depth (1–5)
- `ws_clients` — list of connected WebSocket clients
- `narrative_history` — list of past narrative snippets

### Background Tasks

Two concurrent tasks run per session:

| Task | Function | Behavior |
|------|----------|----------|
| Autonomous escalation | `gradual_ramp_task(exp_id)` | Runs every 10s; ramps HR/GSR/intensity |
| Webcam monitoring | `rppg_monitor_thread(exp_id, loop)` | ~30 FPS; extracts HR via rPPG + detects emotion via DeepFace |

### Intensity Levels

| Range | Level Name |
|-------|-----------|
| 0.0–0.2 | `ambient_unease` |
| 0.2–0.4 | `building_dread` |
| 0.4–0.6 | `active_horror` |
| 0.6–0.8 | `peak_terror` |
| 0.8–1.0 | `absolute_nightmare` |

---

## API Reference

### REST Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Serve `index.html` |
| `POST` | `/api/v1/experience/create` | Create new horror session |
| `POST` | `/api/v1/session/{id}/adapt` | Adaptive difficulty update |
| `POST` | `/api/v1/narrative/generate` | Generate narrative snippet |
| `POST` | `/api/v1/safety/override` | Emergency calm/exit |
| `POST` | `/api/v1/biometrics/{type}` | Ingest biometric data |
| `GET` | `/api/v1/session/{id}/analysis` | Post-session analytics |

### WebSocket Endpoints

| Path | Purpose |
|------|---------|
| `/ws/session/{exp_id}` | Main real-time session channel |
| `/ws/analytics/{exp_id}` | Analytics/metrics stream |

### WebSocket Message Actions (client → server)

```json
{ "action": "solve" }       // Player solved a puzzle (+0.15 intensity)
{ "action": "safe" }        // Emergency calm trigger
{ "action": "exit" }        // Safe word — ends session
{ "action": "biometrics", "hr": 120, "gsr": 0.7 }  // Manual biometric update
```

---

## Safety Systems

The engine has multiple safety mechanisms — **do not remove these**:

1. **Auto-calm:** Triggers if HR > 180 bpm for >10 seconds; resets intensity to 0.3
2. **Manual calm:** `/api/v1/safety/override` or `safe` WebSocket action
3. **Intensity bounds:** Clamped between 0.1 (minimum) and 1.0 (maximum)
4. **Safe word (`exit` action):** Broadcasts exit protocol and resets state

---

## Frontend (`index.html`)

The frontend is a single HTML file with embedded CSS and JavaScript. Key sections:

- **Lines 1–207:** HTML structure + dark horror CSS theme (crimson/black)
- **Lines 268–287:** JS state variables and emotion color mappings
- **Lines 289–363:** UI helpers, intensity bar, ambient audio (Howler.js)
- **Lines 365–452:** WebSocket connection and incoming message handling
- **Lines 454–541:** Session creation, action dispatch, event listeners

The frontend connects to `ws://localhost:8000/ws/session/{exp_id}` automatically after session creation.

---

## Development Conventions

### Code Style

- **Linting:** flake8 with max line length 127, max complexity 10
- **Type hints:** Used throughout (Python typing module)
- **Section delimiters:** ASCII box-drawing characters (`────`) mark major sections in `main.py`
- **Optional imports:** Heavy libraries (OpenCV, TensorFlow, DeepFace) are wrapped in `try/except ImportError` to allow graceful degradation

### Graceful Degradation Pattern

All optional dependencies follow this pattern:

```python
try:
    import some_heavy_library
    FEATURE_AVAILABLE = True
except ImportError:
    FEATURE_AVAILABLE = False
```

Maintain this pattern when adding new optional dependencies.

### Error Handling

- WebSocket disconnects are caught and clients removed from `ws_clients` list
- LLM failures fall back to `FALLBACK_FRAGMENTS` list
- Biometric monitoring failures log warnings and continue

---

## CI/CD

GitHub Actions workflow (`.github/workflows/python-package-conda.yml`):

- Triggers on every push
- Python 3.10, Ubuntu latest
- Runs `flake8` linting (two passes: strict errors + style warnings)
- Runs `pytest` (currently no test files exist)

### Known CI Issues

- The workflow references `environment.yml` (Conda environment file) which **does not exist** — the install step will fail
- No test files exist, so pytest passes vacuously

---

## Known Gaps & Technical Debt

| Issue | Impact | Notes |
|-------|--------|-------|
| No tests | CI passes vacuously | Add pytest files under `tests/` |
| Missing `environment.yml` | CI install step fails | Add or update workflow to use `requirements.txt` |
| In-memory session store | No persistence | Add Redis/DB for production |
| CORS `allow_origins=["*"]` | Security concern | Restrict in production |
| No authentication | Any client can create sessions | Add API key / session tokens |
| Hard-coded Ollama model | `llama3.1:8b` | Make configurable via env var |
| No rate limiting | Abuse potential | Add middleware in production |

---

## Adding New Features

### New REST Endpoint

Add to `main.py` following the existing pattern:

```python
@app.post("/api/v1/your/endpoint")
async def your_handler(payload: YourModel):
    exp_id = payload.experience_id
    if exp_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    # ... logic ...
    return {"status": "ok", "data": ...}
```

### New WebSocket Message Type

Extend the `if/elif` block inside `websocket_session()` around line 784:

```python
elif action == "your_action":
    # handle it
    await _broadcast(exp_id, {"type": "your_response", ...})
```

### Modifying Narrative Generation

Edit `generate_narrative_snippet()` (~line 144). The function accepts:
- `intensity` (float 0.0–1.0)
- `fear_vector` (list of fear types)
- `recursion_level` (int 1–5)
- `detected_emotion` (string)

---

## LLM Configuration

The Ollama model is called at line ~163:

```python
response = ollama.generate(
    model="llama3.1:8b",
    prompt=prompt,
    options={"temperature": 0.85, "num_predict": 120}
)
```

To change model or parameters, edit this call. Ensure `FALLBACK_FRAGMENTS` remains populated for offline use.
