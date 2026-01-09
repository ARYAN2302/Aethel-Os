# Aethel-os: The Local Agentic Secondary OS

Aethel-os is a proof-of-concept for a local, secondary operating system layer that runs atop macOS, powered by a small language model (SLM) performing agentic workflows in a stateful loop.

## Current State

The system is currently operational with the following architectural components and features:

### 1. Agent Architecture
- **Core Engine:** Powered by `google/functiongemma-270m-it` running locally in full precision (FP32) to ensure numerical stability on CPU/MPS.
- **State Management:** Uses a persistent **Scratchpad** (JSON-based) to track goals, plans, and tool execution results across multiple iterations.
- **Hybrid Routing:** Implements "Deterministic Routing" in the kernel to handle structured tasks (multi-step file operations) reliably, bypassing the SLM for known high-probability patterns.
- **Safety Guards:** Includes per-word intent filtering (e.g., regex boundaries for `mac_open_app`), iteration counters, and repeat-action detection to prevent hallucination loops (the "Safari Loop").

### 2. Available Capabilities
- **File System (FS):** Directory creation (`fs_mkdir`), reading/writing files (`fs_read`, `fs_write`), and walking directory trees.
- **Knowledge Graph (KG):** In-memory indexing of local files and simple keyword-based search (`kg_search`).
- **Web Intelligence:** Live web searching via DuckDuckGo integration.
- **System Control:** Deep macOS integration for opening applications and managing workflows.
- **User Collaboration:** Bi-directional communication via the `ask_user` tool and voice input capabilities.

### 3. Frontend
- A React-based dashboard featuring a **PlanBoard** and **Timeline** to visualize the agent's internal reasoning and progress in real-time.

---

## Technical Limitations

- **Model Intelligence:** Using a 270M parameter model is highly efficient but limits complex reasoning. The model occasionally defaults to "known" high-probability tool calls (like Safari) when it encounters ambiguous prompts or logic errors.
- **In-Memory Indexing:** The current Knowledge Graph is ephemeral; indexing is performed during the session and is not yet persisted to a vector database.
- **Inference Latency:** While small, running on CPU/MPS still introduces some latency compared to quantized hardware-accelerated models.

---

## Future Work

1. **Custom LLM Training:** The primary goal is to replace `FunctionGemma` with a custom-trained/fine-tuned model (e.g., a variant of Llama or Phi) specifically optimized for the Aethel OS scratchpad schema and tool-set.
2. **Persistent Vector DB:** Integrate a local database (like ChromaDB or LanceDB) to allow long-term memory and cross-session knowledge retrieval.
3. **Advanced Tooling:** 
   - Shell execution sandbox.
   - Deeper integration with macOS Shortcuts and Automator.
   - Multi-agent collaboration (Swarm-like workflows).
4. **Voice Native Mode:** Enhance `voice.py` to support real-time wake-word detection and low-latency local STT/TTS.
5. **UI Maturation:** Transition from a simple overlay to a full-screen secondary OS dashboard.
