# Johnny System Architecture

This document describes the high-level system architecture, escalation principles, model routing, security levels, and task lifecycles for Johnny.

---

## 1. System Overview

```
+------------------------------------------------------------------+
|                      JOHNNY DESKTOP UI                           |
|       (Tauri 2 Rust Wrapper + React TS + PixiJS Pixel Dog)      |
+------------------------------------------------------------------+
                               |
                   HTTP / SSE / WebSockets
                               v
+------------------------------------------------------------------+
|                    JOHNNY FASTAPI BACKEND                        |
|                                                                  |
|   +-------------------+    +---------------------------------+   |
|   |   API Routers     |    |    Security & Sandbox Level     |   |
|   |  (chat, image,    |    |  (Level 0 safe path validation, |   |
|   |   health, etc.)   |    |   Level 1-3 permission engine)  |   |
|   +-------------------+    +---------------------------------+   |
|             |                                |                   |
|             v                                v                   |
|   +-------------------+    +---------------------------------+   |
|   | Telemetry Engine  |    |     Central Model Router        |   |
|   | (Latency tracker) |    |  (Llama 3.3, MiniMax, DeepSeek) |   |
|   +-------------------+    +---------------------------------+   |
+------------------------------------------------------------------+
                               |
                               v
                    NVIDIA NIM / Remote APIs
```

---

## 2. Screen Observation & Escalation Architecture

Johnny continuous observes local desktop state without incurring high API costs by using a 4-tier escalation policy:

1. **Level 0 (Local Observation)**: Passive frame diffing / Wayland PipeWire capture at low FPS.
2. **Level 1 (Change Detection)**: Fast local perceptual hashing and window focus tracking.
3. **Level 2 (Local OCR & Classification)**: Fast local text extraction when changes occur.
4. **Level 3 (Vision Escalation)**: Call MiniMax M3 only when unstructured screen changes occur or explicit visual inspection is requested.

---

## 3. Centralized Model Routing

Models are never hardcoded in business logic. All models implement the `ModelProvider` interface:

- `Meta Llama 3.3 70B`: General conversation, fast user interaction, streaming text generation.
- `MiniMax M3`: Image & screenshot visual understanding; outputs compact structured JSON.
- `DeepSeek V4 Pro`: Complex coding, debugging, and formal verification tasks.
- `Nemotron`: High-level planning and multi-agent task orchestration.

---

## 4. Security Sandbox Levels

- **Level 0 (Safe Read)**: Read file, inspect directory, git status, process list.
- **Level 1 (Low-Risk Modification)**: Write source code file, run unit test suite, install dependencies.
- **Level 2 (Potentially Destructive)**: Delete files, git reset/force, Docker system prune (Requires user confirmation).
- **Level 3 (Dangerous System Operations)**: Sudo, disk partitioning, network firewall modifications (Explicit confirmation required).

---

## 5. Telemetry & Performance Tracking

Every model request measures:
- `routing_ms`: Time taken to inspect intent and select provider.
- `model_ms`: Time taken by downstream inference provider.
- `total_ms`: End-to-end request duration.
- `tokens`: Prompt & completion token counts.
