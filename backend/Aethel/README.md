# Aethel Project Core

This directory contains the core logic and assets for the Aethel Agent OS.

## System Overview
The backend is a Python-based agentic loop that orchestrates:
- **Model Inference:** `functiongemma-270m-it` on MPS/CPU.
- **Tool Execution:** A registry of macOS and FS tools.
- **State Serialization:** Managed via `core/scratchpad.py`.

## Current Status
- **Loop Gating:** Active defense against Safari hallucination loops.
- **Deterministic Routing:** Implemented in `core/kernel.py` to handle complex multi-step FS tasks reliably.
- **Model Logic:** Fixed AST parsing for JSON tool outputs.

## Future Direction
We plan to migrate from generic SLMs to a specialized model architecture tailored specifically for the Aethel Kernel logic, reducing the need for deterministic fallbacks and increasing the agent's autonomous reasoning depth.
