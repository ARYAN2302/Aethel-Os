

Here is the **Final, Unified Specification** for **Aethel-os**, consolidating the original idea, the architectural decisions, and the debugging fixes we applied (float32 stability, AST parsing, Scratchpad Loop).

Save this as `DESIGN.md` in your project root.

```markdown
# Project Aethel-os: The Stateful Agentic Secondary OS

**Status:** Active Development
**Core Engine:** Google FunctionGemma-270M-IT (Local FP32)
**Paradigm:** Scratchpad-Driven State Management
**Target Platform:** macOS (Python Backend) + React Frontend

---

## 1. Overview

**Aethel-os** is a local, secondary operating system layer that runs atop macOS. It provides a Graphical User Interface (GUI) to interact with a fully autonomous AI agent.

Instead of relying on a massive, context-heavy cloud model, Aethel-os uses a tiny, full-precision 270M parameter model (`functiongemma-270m-it`) to manage a persistent **Scratchpad** (a structured JSON file). The "OS" iteratively reads this Scratchpad, decides the next atomic action (via function calling), executes it using local tools, and writes the result back to the Scratchpad.

This architecture enables **privacy-first**, **offline** automation that is auditable, persistent, and capable of complex multi-step workflows.

### Core Features
- **Local Agent:** 100% Offline inference. No cloud APIs.
- **Knowledge Base:** Local vector indexing of files (`kg_search`, `index_folder`).
- **Web Access:** Live internet search via DuckDuckGo (`search_web`).
- **OS Control:** Direct macOS integration (`mac_open_app`, `fs_read/write`).
- **Bi-Directional:** The agent can pause and ask the user clarifying questions (`ask_user`).
- **Voice Input:** Local macOS Speech-to-Text integration.

---

## 2. Architecture Diagram

```mermaid
flowchart LR
    subgraph "User Space"
        UI[User Apps / Interface]
    end

    subgraph "Aethel-os: Secondary OS Layer (Python)"
        direction LR
        Kernel[Agent Kernel<br/>(The Loop Controller)]
        Scratchpad[(Scratchpad State<br/>(scratchpad.json)]
        Model[FunctionGemma 270M<br/>(PyTorch CPU/MPS)]
        Reg[Capability Registry<br/>(Tool Definitions)]
        IPC[Secure IPC Bus]
    end

    subgraph "macOS Host & Hardware"
        FS[File System]
        DB[Local Data Stores]
        Sys[System APIs (Audio/Wifi/Apps)]
    end

    %% Interactions
    UI <--> IPC
    IPC <--> Kernel

    %% The Core Loop
    Kernel <-->|Read/Write State| Scratchpad
    Kernel -->|Prompt + Tools| Model
    Model -->|Next Action| Kernel
    Kernel -->|Execute Tool| Reg
    Reg -->|Call| FS
    Reg -->|Call| Sys
    Reg -->|Call| DB
    
    %% Feedback
    FS -->|Result| Kernel
    Sys -->|Result| Kernel
    DB -->|Result| Kernel
```

---

## 3. Component Breakdown

### 3.1 The Agent Kernel (Python)
The main Python runtime responsible for the lifecycle of the agent.
- **Responsibilities:**
  - Orchestrates the `while active` loop.
  - Manages serialization/deserialization of `scratchpad.json`.
  - Enforces **Guards** (timeouts, recursion limits, schema validation).
  - Handles IPC with the Host OS via `subprocess`, `os`, or `pyobjc`.

### 3.2 The Model Server
A local inference engine hosting `google/functiongemma-270m-it`.
- **Implementation:** Hugging Face `transformers` + `torch`.
- **Role:** Acts strictly as a **Policy Head**. It maps `Current_State -> Next_Action`.
- **Optimization:** 
  - Running on **CPU (FP32)** for numerical stability (avoiding `inf/nan` errors).
  - Uses **Manual Prompting** (Few-shot examples) to guide the small model.

### 3.3 The Capability Registry
A Python module (`tools/tools.py`) containing classes that define available tools.
- **Function:** Uses `pydantic` to define strict Schemas for every tool (input validation).
- **Categories:**
  - *System:* Alarms, Timers, Volume, Wifi.
  - *File System:* Read, Write, Search.
  - *Knowledge:* Vector search over local files.
  - *Interface:* GUI interaction via Accessibility Tree.
  - *Web:* HTTP search via `httpx`.

### 3.4 The Scratchpad
A persistent JSON structure that acts as the system's RAM.
- **Transparency:** Fully readable and editable in a text editor.
- **Persistence:** Saved to `data/sessions/{id}.json`.
- **Protocol:** 
  - **Planning Phase:** Agent updates `plan` array.
  - **Execution Phase:** Agent calls tools based on plan.
  - **Verification Phase:** Agent checks if `result` satisfied `plan` item.

---

## 4. The Scratchpad Protocol

This is the central technical spec. The Kernel manages this document according to a strict loop.

### 4.1 Scratchpad Schema

Every session creates a `scratchpad.json` instance adhering to this schema:

```json
{
  "meta": {
    "session_id": "uuid",
    "status": "active", // active, awaiting_user_input, completed, error
    "start_time": "ISO8601",
    "iteration_count": 0
  },
  "user_interaction": {
    "pending_question": null,
    "last_user_response": null
  },
  "ui_action": {
    "type": null, // "prompt", "modal", etc.
    "title": null,
    "message": null,
    "options": ["Yes", "No"]
  },
  "plan": [
    {
      "id": 1,
      "description": "High-level subtask description",
      "status": "pending"
    }
  ],
  "knowledge_state": {
    "indexed_directories": [],
    "last_index_time": null
  },
  "steps": [
    {
      "step_id": 1,
      "phase": "planning",
      "action": "tool_name",
      "arguments": {},
      "result": "Tool output string or success boolean",
      "timestamp": "ISO8601"
    }
  ],
  "artifacts": [],
  "final_output": {
    "summary": "Natural language summary for the user",
    "confidence": 0.95
  }
}
```

### 4.2 The Controller Algorithm (The Loop)

The Kernel runs this loop until a termination state is reached.

```python
while scratchpad.meta.status in ["active", "awaiting_user_input"]:
    
    # 1. PERCEPTION
    # Injects user intent + state into prompt
    prompt = construct_prompt(scratchpad, tools)
    
    # 2. DECISION
    # Model generates XML or JSON
    decision = model.generate(prompt)
    
    # 3. ACTION (Parsing)
    # Robust AST/JSON parsing to extract tool name
    if parse(decision):
        tool_name, args = parse(decision)
        
        # 4. EXECUTION
        if tool_name == "ask_user":
            # Sets status to awaiting_user_input
            set_ui_action(question=args.question)
        else:
            # Execute tool via Registry
            result = execute_tool(tool_name, args)
            log_step(tool_name, args, result)
        
        # 5. REFLECTION
        # Update Scratchpad
        save_scratchpad(scratchpad)
    
    # 6. STOP CHECK
    if task_done():
        scratchpad.meta.status = "completed"
        break
```

---

## 5. Capability Registry (Tools)

| Category | Tool Name | Functionality |
| :--- | :--- | :--- |
| **Knowledge**| `index_folder` | Scans files and saves to SQLite-VSS vector store. |
| | `kg_search` | Queries the local vector DB. |
| **Interaction**| `ask_user` | Pauses execution, sends `ui_action` to GUI. |
| **System** | `mac_open_app` | Opens apps via `subprocess`. |
| | `mac_notify` | Sends native macOS Notification. |
| **File** | `fs_read` | Reads file content. |
| | `fs_write` | Writes content to file. |
| | `fs_move` | Moves file. |
| **Web** | `search_web` | Fetches search results from DuckDuckGo via `httpx`. |

---

## 6. Implementation Guide (macOS)

### Tech Stack
- **Backend:** `Python 3.10+`, `FastAPI` (WebSockets), `uvicorn`.
- **Frontend:** `React` (via `Vite`), `Material UI`.
- **AI/Data:** `torch` (Float32), `transformers`, `sentence-transformers`, `sqlite-vss`.
- **Audio:** `SpeechRecognition` (wrapping macOS API).
- **HTTP:** `httpx` (for web tool).

### Project Structure
```text
/aethel_os
├── /backend
│   ├── main.py           # FastAPI entry point
│   ├── /core
│   │   ├── kernel.py     # The Loop (Logic)
│   │   ├── models.py     # Pydantic Schemas
│   │   └── scratchpad.py # State Management
│   ├── /runtime
│   │   ├── model.py      # FunctionGemma wrapper
│   │   ├── prompts.py    # System Prompts & Few-Shot
│   │   └── voice.py      # macOS Speech wrapper
│   ├── /tools
│   │   ├── index.py      # Vector DB logic
│   │   └── tools.py      # Tool Definitions
│   ├── data.db           # SQLite + VSS
│   └── data/
│       └── sessions/    # Scratchpad persistence
├── /frontend
│   ├── /src
│   │   ├── App.jsx       # Main React App
│   │   ├── Timeline.jsx  # Steps Visualizer
│   │   ├── PlanBoard.jsx # Plan Visualizer
│   │   └── ChatOverlay.jsx # UI Action Handler
│   └── package.json
└── DESIGN.md
```

---

## 7. Development Roadmap

### Phase 1: The Core (Kernel + Model)
- [x] Setup Python `kernel.py` with the `while` loop.
- [x] Load `functiongemma-270m-it` in FP32 (CPU Stable).
- [x] Implement `scratchpad.py` Pydantic models.
- [x] Implement manual prompting (Few-shot) for tool calling.

### Phase 2: The Brains (Tools + Vector DB)
- [x] Implement `fs_read`, `fs_write`.
- [x] Implement `kg_index` (loop through files, embed with `all-MiniLM-L6-v2`, save to `sqlite-vss`).
- [x] Implement `kg_search` (query vector DB).
- [x] Implement `mac_open_app` (via `subprocess`).
- [x] Implement `search_web` (via `httpx`).

### Phase 3: The Connection (FastAPI + WebSocket)
- [x] Build `main.py` with FastAPI.
- [x] Create WebSocket endpoint `/ws` to stream `scratchpad.json`.
- [x] Create POST endpoint `/input` to receive user text/voice.
- [x] Implement Robust Parsing (String Slicing + AST).

### Phase 4: The Face (React GUI)
- [ ] Scaffold React app.
- [ ] Build `Timeline.jsx`, `PlanBoard.jsx`.
- [ ] Build `ChatOverlay.jsx` to handle `ui_action` modals.
- [ ] Implement Audio Recording (`MediaRecorder`) and Blob sending.

### Phase 5: The Voice (macOS Integration)
- [ ] Write `voice.py` wrapper using `SpeechRecognition`.
- [ ] Integrate into backend `/audio` endpoint.

---

**End of Specification**
```