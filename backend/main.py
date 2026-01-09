import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from core.kernel import AgentKernel
from core.scratchpad import load_scratchpad
from tools.tools import ToolRegistry
from runtime.voice import transcribe_audio
from core.scratchpad import save_scratchpad
kernel = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- Starting Aethel-os Backend ---")
    
    from runtime.model import load_model
    try:
        load_model()
        print("Model loaded successfully.")
    except Exception as e:
        print(f"FATAL: Failed to load model: {e}")
        raise RuntimeError("Model failed to load")

    tools = ToolRegistry(None)
    global kernel
    kernel = AgentKernel("demo_session", tools)
    asyncio.create_task(kernel.run_loop())
    print("Agent kernel loop started.")

    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WS: Connected to client")
    
    try:
        await websocket.send_text(kernel.scratchpad.model_dump_json())
        
        last_step_count = 0 # Track changes
        
        while True:
            await asyncio.sleep(0.5)
            
            current_steps = len(kernel.scratchpad.steps)
            
            # ONLY SEND IF DATA CHANGED
            if current_steps != last_step_count:
                print(f"WS: State Changed! Sending update ({current_steps} steps)...")
                await websocket.send_text(kernel.scratchpad.model_dump_json())
                last_step_count = current_steps
            
    except Exception as e:
        print(f"WS Error/Disconnect: {e}")

@app.post("/input")
async def handle_user_input(data: dict):
    response = data.get("response")
    if response:
        # 1. Get current interaction object
        # We modify this to avoid triggering Pydantic re-validation on the whole object
        current_inter = kernel.scratchpad.user_interaction
        # 2. Update the response field
        current_inter.last_user_response = response
        # 3. Save back to scratchpad
        kernel.scratchpad.user_interaction = current_inter
        save_scratchpad(kernel.scratchpad)
        
        # 4. Optional: Kick the queue too (legacy, but good for safety)
        await kernel.user_input_queue.put(response)
        
    return {"status": "queued"}

@app.post("/audio")
async def handle_audio(file: UploadFile = File(...)):
    audio_data = await file.read()
    text = transcribe_audio(audio_data)
    if text:
        await kernel.queue_user_response(text)
        return {"text": text}
    return {"error": "Failed to transcribe"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)