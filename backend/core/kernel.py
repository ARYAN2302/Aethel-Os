import asyncio
import os
import json
import re
import ast
from core.models import Scratchpad, Step, UIAction, UserInteraction
from core.scratchpad import save_scratchpad

class AgentKernel:
    def __init__(self, session_id, tools):
        self.session_id = session_id
        self.scratchpad = Scratchpad(meta={"session_id": session_id})
        self.tools = tools
        self.user_input_queue = asyncio.Queue()
        self.tools.kernel = self 
        self.last_action = None  # track last executed tool/args to avoid repeats
        self.reject_count = 0    # track repeated rejections

    def update_plan_direct(self, plan_data):
        self.scratchpad.plan = plan_data

    async def queue_user_response(self, response: str):
        await self.user_input_queue.put(response)

    async def run_loop(self):
        # --- MAIN LOOP START ---
        from runtime.model import generate_response

        async def run_tool(tool: str, tool_args: dict):
            if not hasattr(self.tools, tool):
                return {"error": "unknown_tool"}
            method = getattr(self.tools, tool)
            try:
                return await asyncio.wait_for(method(**tool_args), timeout=10)
            except asyncio.TimeoutError:
                return {"error": "tool_timeout"}

        async def handle_deterministic_request(raw_request: str) -> bool:
            """Handles common requests without relying on the model (SLM reliability)."""
            text = (raw_request or "").strip()
            lower = text.lower()

            # Multi-step file task: create folder + write README + read back
            folder_match = re.search(r"folder\s+named\s+['\"]?([^'\"\n]+)['\"]?", text, flags=re.IGNORECASE)
            content_match = re.search(r"content\s+['\"]([^'\"]+)['\"]", text, flags=re.IGNORECASE)
            wants_read_back = "read" in lower and "back" in lower
            wants_readme = "readme.md" in lower
            wants_create = "create" in lower and "folder" in lower

            if wants_create and wants_readme and content_match and folder_match and wants_read_back:
                folder_name = folder_match.group(1).strip()
                readme_path = os.path.join(folder_name, "README.md")
                file_content = content_match.group(1)

                plan_items = [
                    f"Create folder {folder_name}",
                    f"Write {readme_path}",
                    f"Read {readme_path}"
                ]
                await run_tool("update_plan", {"plan": plan_items})
                await run_tool("fs_mkdir", {"path": folder_name})
                await run_tool("fs_write", {"path": readme_path, "content": file_content})
                read_result = await run_tool("fs_read", {"path": readme_path})

                self.scratchpad.steps.append(Step(
                    step_id=len(self.scratchpad.steps) + 1,
                    phase="execution",
                    action="fs_read",
                    arguments={"path": readme_path},
                    result=str(read_result)
                ))
                self.scratchpad.final_output = {"summary": read_result}
                self.scratchpad.meta.status = "completed"
                self.scratchpad.user_interaction.last_user_response = None
                save_scratchpad(self.scratchpad)
                return True

            # Simple deterministic routing helpers
            if lower.startswith("index folder "):
                path = text.split(" ", 2)[2].strip()
                result = await run_tool("index_folder", {"path": path})
                self.scratchpad.steps.append(Step(step_id=len(self.scratchpad.steps) + 1, phase="execution", action="index_folder", arguments={"path": path}, result=str(result)))
                save_scratchpad(self.scratchpad)
                return True

            if lower.startswith("search kg for "):
                query = text.split(" ", 3)[3].strip()
                result = await run_tool("kg_search", {"query": query})
                self.scratchpad.steps.append(Step(step_id=len(self.scratchpad.steps) + 1, phase="execution", action="kg_search", arguments={"query": query}, result=str(result)))
                save_scratchpad(self.scratchpad)
                return True

            return False

        while self.scratchpad.meta.status in ["active", "awaiting_user_input"]:
            
            # 1. Wait for user intent (Only if not set)
            if not self.scratchpad.user_interaction.last_user_response:
                await asyncio.sleep(1)
                continue

            # 2. Handle Tool-Induced Pauses (ask_user)
            if self.scratchpad.meta.status == "awaiting_user_input":
                print("Waiting for user input...")
                response = await self.user_input_queue.get()
                # DO NOT CLEAR last_user_response HERE (Keep context)
                self.scratchpad.user_interaction.last_user_response = response
                self.scratchpad.meta.status = "active"
                self.scratchpad.ui_action = UIAction()
                save_scratchpad(self.scratchpad)
                continue

            # 3. Generate Decision
            print("Thinking...")
            # Deterministic routing for known multi-step file tasks
            if await handle_deterministic_request(self.scratchpad.user_interaction.last_user_response or ""):
                break
            # Filter mac_open_app from schema if no explicit open intent
            last_intent = (self.scratchpad.user_interaction.last_user_response or "").lower()
            # Use word boundaries so strings like "mac_open_app" don't count as user intent.
            has_open_intent = re.search(r"\b(open|launch|start|run)\b", last_intent) is not None
            excluded_tools = [] if has_open_intent else ["mac_open_app"]
            allowed_tools = set(getattr(self.tools, "tools", {}).keys()) - set(excluded_tools)
            tools_schema = self.tools.get_schema_string(exclude=excluded_tools)
            raw_output = generate_response(self.scratchpad, tools_schema)
            
            print(f"--- Model Raw Output ---\n{raw_output}\n--- End Output ---")

            # --- SMART PARSER ---
            # Robustly capture the first function-call block
            function_match = re.search(r'<start_function_call>\s*call:([\w_]+)\s*(\{.*?\})\s*<end_function_call>', raw_output, re.DOTALL)
            
            if function_match:
                tool_name = function_match.group(1)
                args_str = function_match.group(2)
                # Normalize any escaped-brace artifacts the model might copy from examples
                args_str = args_str.replace('{"{"}', '{').replace('{"}"}', '}')

                # Enforce tool availability strictly at the controller layer.
                if tool_name not in allowed_tools:
                    print(f"Tool '{tool_name}' is not allowed right now. Retrying...")
                    self.scratchpad.meta.iteration_count += 1
                    # Nudge the model away from the forbidden tool without changing user intent
                    self.scratchpad.user_interaction.last_user_response = (
                        (self.scratchpad.user_interaction.last_user_response or "")
                        + "\n\nIMPORTANT: You must only call a tool from AVAILABLE TOOLS. "
                        + "Do NOT call the forbidden tool."
                    )
                    save_scratchpad(self.scratchpad)
                    await asyncio.sleep(0.2)
                    continue
                
                # --- REJECT TEMPLATES ---
                if tool_name == "tool_name" or tool_name == "tool_name{args}" or args_str in ["{args}", "{arg:value}"]:
                    print("Model is hallucinating format definitions. Retrying...")
                    await asyncio.sleep(1)
                    continue
                   

                try:
                    try:
                        args = json.loads(args_str)
                    except json.JSONDecodeError:
                        print("JSON failed, trying literal_eval...")
                        args = ast.literal_eval(args_str)
                        
                except Exception as e:
                    print(f"Parsing Error: {e}")
                    self.scratchpad.meta.status = "error"
                    save_scratchpad(self.scratchpad)
                    break

                # Intent alignment / correction based on user text
                raw_request = self.scratchpad.user_interaction.last_user_response or ""
                user_request = raw_request.lower().strip()

                if tool_name == "mac_open_app":
                    # Require explicit open intent; otherwise hard-block
                    open_intents = ["open", "launch", "start", "run"]
                    if not any(word in user_request for word in open_intents):
                        print("App open rejected: no open intent detected. Stopping.")
                        self.scratchpad.meta.status = "completed"
                        self.scratchpad.user_interaction.last_user_response = None
                        save_scratchpad(self.scratchpad)
                        break
                    # Align app_name with user intent when the model defaults incorrectly (e.g., Safari)
                    app_map = {
                        "notes": "Notes",
                        "note": "Notes",
                        "safari": "Safari",
                        "chrome": "Google Chrome",
                        "google chrome": "Google Chrome",
                        "finder": "Finder",
                        "terminal": "Terminal",
                        "iterm": "iTerm",
                        "calendar": "Calendar",
                        "spotify": "Spotify"
                    }
                    resolved_app = None
                    for key, app in app_map.items():
                        if key in user_request:
                            resolved_app = app
                            break
                    # Heuristic: if the user says "open X" then take X as app name (title-cased)
                    if not resolved_app and user_request.startswith("open "):
                        candidate = raw_request.split(" ", 1)[1].strip()
                        if candidate:
                            resolved_app = candidate.title()
                    if resolved_app:
                        args["app_name"] = resolved_app
                else:
                    # reset rejection counter when tool changes away from mac_open_app
                    self.reject_count = 0

                print(f"Executing: {tool_name} with {args}")

                # Validate common placeholders / missing args
                if tool_name == "fs_read":
                    path = (args or {}).get("path")
                    if not isinstance(path, str) or not path or path.strip() in {"file.txt", "path/to/file", "your_file.txt"}:
                        self.scratchpad.meta.status = "awaiting_user_input"
                        self.scratchpad.ui_action = UIAction(
                            type="prompt",
                            title="Input Needed",
                            message="Which file path should I read? (e.g., backend/runtime/model.py)",
                            options=[]
                        )
                        save_scratchpad(self.scratchpad)
                        continue
                    if not os.path.exists(path):
                        self.scratchpad.meta.status = "awaiting_user_input"
                        self.scratchpad.ui_action = UIAction(
                            type="prompt",
                            title="File Not Found",
                            message=f"File not found: {path}. Provide an existing path.",
                            options=[]
                        )
                        save_scratchpad(self.scratchpad)
                        continue

                # Prevent executing the exact same tool/args twice in a row
                if self.last_action and self.last_action == (tool_name, args):
                    print("Repeat action detected; stopping to avoid loop.")
                    self.scratchpad.meta.status = "completed"
                    save_scratchpad(self.scratchpad)
                    break

                if tool_name == "ask_user":
                    self.scratchpad.meta.status = "awaiting_user_input"
                    self.scratchpad.ui_action = UIAction(
                        type="prompt",
                        title="Input Needed",
                        message=args.get("question", "Continue?"),
                        options=["Yes", "No"]
                    )
                    save_scratchpad(self.scratchpad)
                
                else:
                    if hasattr(self.tools, tool_name):
                        method = getattr(self.tools, tool_name)
                        try:
                            result = await asyncio.wait_for(method(**args), timeout=10)
                        except asyncio.TimeoutError:
                            result = {"error": "tool_timeout"}
                        
                        self.scratchpad.steps.append(Step(
                            step_id=len(self.scratchpad.steps)+1,
                            phase="execution",
                            action=tool_name,
                            arguments=args,
                            result=str(result)
                        ))
                        # After any tool, clear user input; keep loop active only if still active
                        self.last_action = (tool_name, args)
                        self.scratchpad.user_interaction.last_user_response = None
                        save_scratchpad(self.scratchpad)
            
            else:
                # 4. Check for "Done" condition
                if "done" in raw_output.lower() or "task completed" in raw_output.lower():
                    self.scratchpad.meta.status = "completed"
                    self.scratchpad.final_output = {"summary": raw_output}
                    self.scratchpad.user_interaction.last_user_response = None # Clear only on completion
                    save_scratchpad(self.scratchpad)
                    break
                
                # If pure text but not "done", just print it
                print("Model returned pure text.")
                break
            
            # Only clear input if status is no longer active (completed/error)
            if self.scratchpad.meta.status not in ["active", "awaiting_user_input"]:
                self.scratchpad.user_interaction.last_user_response = None
                save_scratchpad(self.scratchpad)

            if self.scratchpad.meta.iteration_count > 50:
                print("Max iteration count reached.")
                self.scratchpad.meta.status = "error"
                save_scratchpad(self.scratchpad)
                break

            # Track loop iterations to avoid infinite runs
            self.scratchpad.meta.iteration_count += 1

            # Safety: if no new user input and no status change for too long, stop the loop
            if self.scratchpad.meta.iteration_count > 20 and not self.scratchpad.user_interaction.last_user_response:
                print("No new input; stopping loop to avoid repeats.")
                self.scratchpad.meta.status = "completed"
                save_scratchpad(self.scratchpad)
                break

            await asyncio.sleep(1)