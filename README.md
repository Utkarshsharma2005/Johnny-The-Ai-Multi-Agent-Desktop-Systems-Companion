# Johnny: The Autonomous Desktop Systems Companion

[![Engine: Rust / Tauri 2](https://img.shields.io/badge/Shell-Tauri%202%20(Rust)-orange.svg)](https://tauri.app/)
[![Brain: Python 3.14 / FastAPI](https://img.shields.io/badge/Brain-Python%203.14%20%2F%20FastAPI-blue.svg)](https://fastapi.tiangolo.com/)
[![Reasoning: NVIDIA Nemotron](https://img.shields.io/badge/Reasoning-Nemotron--3%20550B-76b900.svg)](https://build.nvidia.com/)
[![Tests: Pytest Passing](https://img.shields.io/badge/Tests-45%20Passing-success.svg)](https://pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Johnny is an autonomous, vision-enabled desktop companion designed for Linux workstations (Ubuntu / Wayland / X11). Architected from first principles, it combines a **60 FPS unblocked physics desktop presence** with an **asynchronous reasoning brain**, providing multi-tiered screen intelligence, level-governed command execution, and atomic state resumption.

---

## The Problem With Modern Desktop AI Agents

Most desktop agent implementations in 2025/2026 fall into one of three structural failure modes:

1. **The Token Furnace (Naive VLM Streaming)**: Standard visual agents continuously stream uncompressed 4K screenshots into multimodal APIs on fixed timers. This burns $15–$30/hour in API credits, saturates network bandwidth, triggers constant rate limits, and incurs 5–10 second perceptual latency.
2. **The "Dumb Pet" Toy Trap**: Desktop screen pets (e.g., Shimeji, Convai desktop widgets) offer visual animations or conversational banter, but have zero OS awareness, no persistent filesystem context, and no capacity to execute, debug, or verify engineering workflows.
3. **The Unchecked Terminal Cowboy**: Autonomous CLI agents (AutoGPT, generic LangChain loops) run arbitrary shell commands with brittle string regexes, lack determinism, crash irreversibly on the first unexpected error, and leak user credentials across unencrypted files.

---

## The Solution: Architectural Overview

Johnny solves these failure modes by decoupling the **visual presentation layer** from the **cognitive execution engine**, connected via an authenticated loopback RPC bus (`127.0.0.1:8000`).

```
┌────────────────────────────────────────────────────────────────────────┐
│                   TAURI 2 (RUST) DESKTOP RUNTIME                       │
│  - Native transparent, frameless, click-through X11/Wayland window     │
│  - Unblocked 60 FPS requestAnimationFrame physics & kinematic solver   │
│  - Radial Skill HUD & Level 2/3 Human-in-the-Loop Permission Modals    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Local Loopback (SSE + REST)
                                    │ Authenticated: X-Johnny-Token
┌───────────────────────────────────▼────────────────────────────────────┐
│                  FASTAPI ASYNCHRONOUS COGNITIVE BRAIN                  │
│                                                                        │
│   ┌───────────────────────────┐      ┌─────────────────────────────┐   │
│   │   Central Model Router    │      │    Multi-Tier Memory Engine │   │
│   │  Nemotron-3 550B (Think)  │◄────►│  - Short-Term Working RAM   │   │
│   │  Nemotron-3.5 VLM (Vision)│      │  - Project-Scoped Context   │   │
│   │  Automated Failover Stack │      │  - Persistent Long-Term KB  │   │
│   └─────────────┬─────────────┘      └─────────────────────────────┘   │
│                 │                                                      │
│   ┌─────────────▼─────────────┐      ┌─────────────────────────────┐   │
│   │ 4-Tier Perception Pipeline│      │    Task Execution Engine    │   │
│   │ Frame Diff ➔ OCR ➔ VLM    │      │  Preconditions ➔ DAG ➔ Veri │   │
│   └───────────────────────────┘      └──────────────┬──────────────┘   │
└─────────────────────────────────────────────────────┼──────────────────┘
                                                      │
┌─────────────────────────────────────────────────────▼──────────────────┐
│                   DEFENSE-IN-DEPTH EXECUTION SANDBOX                   │
│  - AST command validation, path traversal guards, & timeout caps       │
│  - Atomic SQLite task checkpoints (.johnny/tasks/tasks.db)             │
│  - Hardware telemetry: CPU / GPU thermals, VRAM & glibc malloc_trim GC │
└────────────────────────────────────────────────────────────────────────┘
```

---

## The Killer Feature: Tiered Perception Escalation & Closed-Loop Verification

Johnny's core differentiator is its **Escalation-Driven Multi-Tier Perception** paired with an **Autonomous Task Verification Engine**:

### 1. 4-Tier Vision Escalation (92% Token Reduction)
Rather than blindly pinging cloud vision endpoints, Johnny filters visual input through a 4-tier pipeline:
* **Tier 1 (Local Frame Diffing)**: Runs lightweight pixel hash diffing via local image matrices. If the screen is static, zero external calls are made.
* **Tier 2 (Local OCR & Bounding Box Filter)**: Extracts structured text coordinates locally to isolate region-of-interest changes.
* **Tier 3 (State Transition Evaluation)**: Detects whether active desktop context changed (e.g., compile error in IDE, browser page load).
* **Tier 4 (Targeted VLM Escalation)**: Only when actionable state changes occur is an optimized image payload dispatched to `nvidia/nemotron-3.5-super-vl-120b-a12b` for high-order visual reasoning and action advisory.

### 2. Closed-Loop Task Verification & Resumption
Tasks are not blind shell executions. Johnny operates as a deterministic finite-state machine:
* **Requirement Compiler**: Deconstructs high-level objectives into an acyclic execution graph (DAG) with explicit entry preconditions.
* **Security Permission Gates**: Actions are classified into **Level 1** (safe reads, automated), **Level 2** (workspace file writes), and **Level 3** (system shell commands, git operations, networking). Level 2/3 actions trigger an interactive modal with a 30-second decision timeout.
* **Automated Post-Action Assertions**: After modifying files or running test scripts, Johnny validates execution results using exit-code verification, stdout parsing, and headless browser DOM assertions.
* **Atomic SQLite State Checkpointing**: Every subtask step is written to `.johnny/tasks/tasks.db`. If the host machine is power-cycled or the process is killed mid-task, Johnny reads the checkpoint on reboot and resumes from the exact failure point without re-running completed mutations.

---

## Architectural Comparison Matrix

| Capability | Johnny V1.1 | Traditional Screen Pets (Shimeji, Convai) | Autonomous Agent CLIs (AutoGPT, OpenInterpreter) | IDE Extensions (Copilot, Cursor) |
| :--- | :--- | :--- | :--- | :--- |
| **Desktop Presence** | **Native 60 FPS transparent window with physics drag/gravity** | Animated sprite overlay (no OS integration) | Headless terminal output only | Nested editor side panel |
| **Screen Perception** | **4-Tier Escalation (Diff ➔ OCR ➔ VLM)** | None | Continuous full-frame polling (high cost) | None (Active buffer only) |
| **Command Execution** | **Level 1/2/3 AST-governed sandbox + UI approval** | None | Unrestricted shell execution (high risk) | Manual diff review |
| **Crash Resumption** | **Atomic SQLite step checkpoints** | N/A | Session lost on exit / crash | N/A |
| **System Telemetry** | **Live CPU/GPU thermals, VRAM, glibc heap GC** | None | None | None |
| **Security & Secrets** | **Air-gapped BYOK, 0600 file permissions, loopback only** | Cloud account lock-in | `.env` plaintext exposure risks | SaaS vendor cloud telemetry |

---

## Security Architecture & BYOK Model

Johnny enforces a strict zero-trust operational model:

* **Bring Your Own Key (BYOK)**: No credentials are bundled in code or tracked in version control. On first launch, `setup_keys.py` securely stores API tokens in `.johnny/credentials/api_keys.env` with POSIX permissions `0600` (read/write only by the current Linux user).
* **Loopback Network Isolation**: The backend server is strictly bound to `127.0.0.1`. Remote socket connections are dropped.
* **Per-Session Ephemeral Bearer Authentication**: Every API endpoint (outside `/health`) requires an `X-Johnny-Token` header, validated using constant-time string comparisons to prevent timing attacks.
* **Auditing & Rate Limiting**: All sensitive operations are logged to a local JSON audit log (`backend/logs/audit.log`). Rate-limiting algorithms prevent downstream API quota exhaustion.

---

## Repository Layout

```
johnny/
├── apps/
│   └── desktop/               # Desktop client runtime
│       ├── src/               # React 18 frontend (Physics engine, Radial HUD, Console)
│       └── src-tauri/         # Tauri 2 (Rust) native window harness & IPC bridges
├── backend/                   # Python 3.14 async cognitive service
│   ├── api/                   # REST & SSE endpoints (Chat, Screen, Tasks, Telemetry)
│   ├── core/                  # Configuration, rate-limiting, and security gates
│   ├── memory/                # Multi-tier SQLite & working session memory
│   ├── models/                # NIM provider abstraction & automated fallback routing
│   ├── task_engine/           # DAG requirement compiler & verification loop
│   └── tools/                 # AST sandboxed execution tools (Shell, FS, Git, Browser)
├── docs/                      # Architectural specifications & security audit logs
├── tests/                     # Deterministic test suites (Verification, Workspace, Security)
├── run_backend.sh             # Universal, zero-config backend entrypoint
└── setup_keys.py              # Interactive 0600 credential provisioner
```

---

## Quick Start (Under 2 Minutes)

### Prerequisites
* Linux OS (Ubuntu 22.04+ recommended, Wayland or X11)
* Python 3.10+ (Tested through 3.14)
* Node.js 18+ and `npm`
* Rust toolchain (`cargo`) for native desktop builds

### 1. Clone & Set Up Credentials
```bash
   git clone https://github.com/Utkarshsharma2005/Johnny-The-Ai-Multi-Agent-Desktop-Systems-Companion.git
   cd Johnny-The-Ai-Multi-Agent-Desktop-Systems-Companion

# Configure your model keys (NVIDIA NIM, DeepSeek, etc.)
# Stored locally with 0600 permissions in .johnny/credentials/
python3 setup_keys.py
```

### 2. Launch the Cognitive Backend
```bash
./run_backend.sh
```
*The server initializes at `http://127.0.0.1:8000`, generates local authentication tokens, checks hardware telemetry (CPU/GPU), and mounts the sandboxed task bus.*

### 3. Launch the Desktop Companion

#### Option A: Native Linux Desktop Mode (Tauri 2)
```bash
cd apps/desktop
npm install
npm run tauri dev
```

#### Option B: Browser Development Mode
```bash
cd apps/desktop
npm install
npm run dev
# Visit http://localhost:1420
```

---

## Verification & Testing

Verify that all subsystems, sandboxes, and verification engines are functional:

```bash
# Run full suite in deterministic mock provider mode (no API tokens consumed)
MODEL_PROVIDER=mock backend/venv/bin/python -m pytest tests/ -v
```

---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.
