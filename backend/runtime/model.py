import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
import torch
import re
from transformers import AutoTokenizer, AutoModelForCausalLM
from core.models import Scratchpad
from runtime.prompts import AETHEL_SYSTEM_PROMPT

LOCAL_MODEL_PATH = os.path.join(os.path.dirname(__file__), "../model")
DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"

tokenizer = None
model = None

def load_model():
    global tokenizer, model

    if not os.path.exists(LOCAL_MODEL_PATH):
        raise FileNotFoundError(f"Model not found at {os.path.abspath(LOCAL_MODEL_PATH)}.")

    print(f"Loading model from local path: {os.path.abspath(LOCAL_MODEL_PATH)}")
    print(f"Running on device: {DEVICE}")

    tokenizer = AutoTokenizer.from_pretrained(
        LOCAL_MODEL_PATH,
        local_files_only=True,
        trust_remote_code=True,
        # fix_mistral_regex can fail on some tokenizer builds; disable to avoid Split assignment errors
        # fix_mistral_regex=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        LOCAL_MODEL_PATH,
        dtype=torch.float32,
        device_map=DEVICE,
        local_files_only=True,
        trust_remote_code=True
    )

    print("Model loaded successfully.")

def _extract_first_function_call(text: str) -> str:
    """
    Returns the first <start_function_call>...</end_function_call> block if present,
    otherwise returns the original text trimmed.
    """
    m = re.search(r"<start_function_call>.*?<end_function_call>", text, flags=re.DOTALL)
    return m.group(0).strip() if m else text.strip()

def generate_response(scratchpad: Scratchpad, tools_list_str: str):
    user_intent = scratchpad.user_interaction.last_user_response or "No input."

    # Force the model to return a single, valid JSON function call.
    prompt = f"""
{AETHEL_SYSTEM_PROMPT}

AVAILABLE TOOLS:
{tools_list_str}

USER REQUEST:
{user_intent}

INSTRUCTION (STRICT):
- Reply with exactly ONE function call block.
- Use only a tool name from AVAILABLE TOOLS.
- Arguments MUST be valid JSON (double quotes for keys/strings).
- If there are no arguments, use an empty object: {{}}.
- Never output placeholders like arg/value/tool_name; use real parameter names and values.
- Output NOTHING except the function call block.

Example format:
<start_function_call>call:fs_read{{"path": "file.txt"}}<end_function_call>

Assistant:
"""

    inputs = tokenizer(prompt, return_tensors="pt").to(DEVICE)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=128,
            do_sample=False,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.eos_token_id,
        )

    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return _extract_first_function_call(decoded)