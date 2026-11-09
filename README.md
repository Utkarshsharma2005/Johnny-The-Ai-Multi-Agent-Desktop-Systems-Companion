# JOHNNY 🐶
> **Multimodal Desktop AI Pet & Proactive Assistant for Linux (Ubuntu / Wayland)**

Johnny is a desktop AI companion designed for Ubuntu Linux. Appearing as an expressive, interactive desktop pet, Johnny continuously monitors system context, escalates vision and reasoning to specialized AI models, and autonomously executes desktop tasks within a secure permission sandbox.

---

## ⚠️ SECURITY WARNINGS — READ BEFORE RUNNING

1. **Never commit secrets.** `.env`, `*.key`, `*.pem` are gitignored. If you
   accidentally commit a key, **rotate it immediately** — cleaning git history
   is not enough. See `docs/SECURITY_HARDENING.md`.
2. **No API keys ship with this project.** On first run `./run_backend.sh`
   launches a key wizard: it asks for your NVIDIA NIM key once and stores it
   in `.johnny/credentials/api_keys.env` (0600, gitignored) — never again
   needed, never committed. Status: `python setup_keys.py --status`.
3. **API auth is enabled.** All `/api/v1/*` endpoints (except health)
   require `X-Johnny-Token`. The token auto-generates into
   `.johnny/credentials/api_token` on first run — treat that file like a
   password. Details: `docs/API_SECURITY.md`.
4. **Rate limiting is active** (e.g. chat 10/min, tools 15/min). Exceeding
   limits returns `429` with `Retry-After`.
5. **Tools are sandboxed, not magic.** Level 2/3 tool actions require your
   explicit approval; the old auto-approval behavior was removed.
6. **Audit everything.** Sensitive actions are logged in JSON to
   `backend/logs/audit.log`. Review it periodically.
7. Keep the backend bound to `127.0.0.1` (default). Never expose it to a
   network without full re-evaluation.

---

## 🌟 Key Features

- **Physics-Driven Desktop Pet (V1.1)**:
  - 60 FPS physics engine with realistic desktop gravity, drag momentum, and window collision boundaries.
  - Autonomous behavioral state director: idle wandering, micro-sleep, drag reactions, thinking, and celebration animations.
  - Radial SVG **Skill Wheel** for quick contextual actions (Chat, Tasks, Memory, Vision, Settings).
  - Floating animated **Speech Bubbles** with streaming typewriter tokens and quick-action chips.
  - **Vision Intelligence Badge**: Live cooldown ring tracking background screen observation.
- **Glassmorphic Console Panel**:
  - 11 specialized tabs: Chat, Browser, Memory, Screen, Requirements, Tools, Tasks, Verification, Models, Telemetry, and Settings.
- **AI Brain & Centralized Model Router**:
  - Seamless abstraction over specialized models via NVIDIA NIM (Meta Llama 3.3 70B, MiniMax M3, DeepSeek R1, Nemotron).
  - Multi-model orchestration: Ensemble, Cascade, and Fusion strategies with evidence merging.
- **Multi-Tier Memory Subsystem**:
  - Short-term session memory, project-specific context, and persistent long-term storage.
- **Sandboxed Workspace Tools & Autonomous Execution**:
  - Automated Terminal (with output capping and timeout limits), Filesystem, Git, Docker, and Playwright Browser automation.
  - Pre-task Requirement Compiler & Closed-Loop Verification Engine.
- **Atomic Crash Resumption**:
  - State saved to `.johnny/tasks/` for instant recovery across unexpected interruptions.

---

## 🛠 Tech Stack

- **Desktop Shell**: Tauri 2 (Rust) — native GTK frameless, transparent, always-on-top window
- **Frontend UI & Physics**: React 18, TypeScript, Vite, CSS Design Tokens, Lucide icons
- **Backend API**: Python 3.14, FastAPI, `asyncio`, `uvicorn`, Playwright
- **Testing**: `pytest`, `httpx` (45 tests passing)

---

## 🚀 Quick Start

### 1. Run Automated Tests
```bash
MODEL_PROVIDER=mock backend/venv/bin/python -m pytest tests/ -v
```

### 2. Start the Backend Brain
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

### 3. Run the Desktop Pet

#### Mode A: Web Dev Mode (Browser Preview)
```bash
cd apps/desktop
npm run dev
# Visit http://localhost:1420
```

#### Mode B: Native Linux Desktop Mode (Tauri 2)
```bash
cd apps/desktop
npm run tauri dev
```

---

## 📄 Documentation

- [Project Status & Health](file:///home/anshu-04/Projects/johnny/docs/STATUS.md)
- [Release Roadmap](file:///home/anshu-04/Projects/johnny/docs/roadmap.md)
- [Development Guide](file:///home/anshu-04/Projects/johnny/docs/development.md)
- [UI Reference Analysis](file:///home/anshu-04/Projects/johnny/docs/UI_REFERENCE_ANALYSIS.md)
- [Architecture Specification](file:///home/anshu-04/Projects/johnny/architecture.md)
- [Model Routing Architecture](file:///home/anshu-04/Projects/johnny/docs/model-routing.md)
- [Security & Permission Sandbox](file:///home/anshu-04/Projects/johnny/docs/security.md)
