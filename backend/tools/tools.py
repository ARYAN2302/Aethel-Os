import os
import shutil
import subprocess
from datetime import datetime
from typing import Dict, Any, List

from core.models import PlanItem

import httpx
from bs4 import BeautifulSoup

class ToolRegistry:
    def __init__(self, kernel):
        self.kernel = kernel
        # Lightweight in-memory index store: {"path": str, "content": str}
        self._index: List[Dict[str, str]] = []
        self.tools = {
            "ask_user": self.ask_user,
            "update_plan": self.update_plan,
            "index_folder": self.index_folder,
            "kg_search": self.kg_search,
            "fs_read": self.fs_read,
            "fs_write": self.fs_write,
            "fs_move": self.fs_move,
            "fs_mkdir": self.fs_mkdir,
            "mac_open_app": self.mac_open_app,
            "search_web": self.search_web # <--- NEW TOOL
        }

    async def ask_user(self, question: str) -> Dict:
        return {"special": "ask_user", "question": question}

    async def update_plan(self, plan: list) -> Dict:
        # Coerce list[str] into PlanItem objects
        if isinstance(plan, list):
            plan_items = []
            for idx, p in enumerate(plan, start=1):
                if isinstance(p, dict) and "description" in p:
                    plan_items.append(PlanItem(id=idx, description=p.get("description", ""), status=p.get("status", "pending")))
                else:
                    plan_items.append(PlanItem(id=idx, description=str(p), status="pending"))
            self.kernel.update_plan_direct(plan_items)
            return {"status": "plan_updated", "count": len(plan_items)}
        return {"error": "invalid_plan_format"}

    async def index_folder(self, path: str) -> Dict:
        if not os.path.exists(path):
            return {"error": "Directory not found"}
        file_count = 0
        indexed = 0
        self._index.clear()
        for root, dirs, files in os.walk(path):
            for fname in files:
                file_count += 1
                fpath = os.path.join(root, fname)
                try:
                    # Skip binary/large files
                    if os.path.getsize(fpath) > 200_000:
                        continue
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                    self._index.append({"path": fpath, "content": content})
                    indexed += 1
                except Exception:
                    continue
        if path not in self.kernel.scratchpad.knowledge_state.indexed_directories:
            self.kernel.scratchpad.knowledge_state.indexed_directories.append(path)
        self.kernel.scratchpad.knowledge_state.last_index_time = datetime.now().isoformat()
        return {"status": "indexed", "files_seen": file_count, "files_indexed": indexed}

    async def kg_search(self, query: str) -> Dict:
        if not query:
            return {"error": "empty_query"}
        if not self._index:
            return {"error": "index_empty"}
        q = query.lower()
        tokens = [t for t in q.split() if t]
        hits = []
        for item in self._index:
            text = item["content"].lower()
            fname = os.path.basename(item["path"]).lower()
            score = 0
            for t in tokens:
                score += text.count(t)
                score += fname.count(t) * 2
            if score > 0:
                snippet = item["content"][:400]
                hits.append({"path": item["path"], "snippet": snippet, "score": score})
        hits = sorted(hits, key=lambda h: h["score"], reverse=True)[:5]
        return {"results": hits}

    async def fs_read(self, path: str) -> Dict:
        if not os.path.exists(path): return {"error": "File not found"}
        try:
            with open(path, "r", encoding='utf-8') as f: return {"content": f.read()}
        except UnicodeDecodeError:
            return {"error": "Binary file or encoding issue."}

    async def fs_write(self, path: str, content: str) -> Dict:
        # Ensure parent directory exists
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding='utf-8') as f: f.write(content)
        return {"status": "success"}

    async def fs_mkdir(self, path: str) -> Dict:
        try:
            os.makedirs(path, exist_ok=True)
            return {"status": "created", "path": path}
        except Exception as e:
            return {"error": str(e)}

    async def fs_move(self, src: str, dst: str) -> Dict:
        if not os.path.exists(src): return {"error": "Source not found"}
        shutil.move(src, dst)
        return {"status": "moved"}

    async def mac_open_app(self, app_name: str) -> Dict:
        subprocess.run(["open", "-a", app_name])
        return {"status": "opened"}

    # --- NEW INTERNET TOOL ---
    async def search_web(self, query: str) -> Dict:
        """Performs a web search using DuckDuckGo and returns text snippets."""
        url = f"https://html.duckduckgo.com/html/?q={query}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                # Parse HTML to get snippets
                soup = BeautifulSoup(response.text, "html.parser")
                results = []
                for result in soup.select(".result__body")[:5]: # Top 5 results
                    title = result.select_one(".result__title")
                    snippet = result.select_one(".result__snippet")
                    if title and snippet:
                        results.append({
                            "title": title.get_text(),
                            "snippet": snippet.get_text()
                        })
                return {"results": results}
        except Exception as e:
            return {"error": str(e)}

    def get_schema_string(self, exclude: list | None = None):
        exclude = set(exclude or [])
        entries = [
            ("ask_user", '{"question": "string"}'),
            ("update_plan", '{"plan": ["item1", "item2"]}'),
            ("index_folder", '{"path": "string"}'),
            ("kg_search", '{"query": "string"}'),
            ("fs_read", '{"path": "string"}'),
            ("fs_write", '{"path": "string", "content": "string"}'),
            ("fs_mkdir", '{"path": "string"}'),
            ("fs_move", '{"src": "string", "dst": "string"}'),
            ("mac_open_app", '{"app_name": "string"}'),
            ("search_web", '{"query": "string"}')
        ]
        lines = ["Tools (use JSON args):"]
        for name, sig in entries:
            if name in exclude:
                continue
            lines.append(f"- {name} {sig}")
        return "\n".join(lines)