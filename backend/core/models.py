from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime

class Step(BaseModel):
    step_id: int
    phase: str
    action: Optional[str] = None
    arguments: Optional[Dict] = None
    result: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class PlanItem(BaseModel):
    id: int
    description: str
    status: str = "pending"

class UIAction(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = None
    message: Optional[str] = None
    options: Optional[List[str]] = None

class KnowledgeState(BaseModel):
    indexed_directories: List[str] = []
    last_index_time: Optional[str] = None

class UserInteraction(BaseModel):
    pending_question: Optional[str] = None
    last_user_response: Optional[str] = None

class ScratchpadMeta(BaseModel):
    session_id: str
    status: str = "active" # active, awaiting_user_input, completed, error
    start_time: str = Field(default_factory=lambda: datetime.now().isoformat())
    iteration_count: int = 0

class Scratchpad(BaseModel):
    meta: ScratchpadMeta
    user_interaction: UserInteraction = Field(default_factory=UserInteraction)
    ui_action: UIAction = Field(default_factory=UIAction)
    plan: List[PlanItem] = []
    knowledge_state: KnowledgeState = Field(default_factory=KnowledgeState)
    steps: List[Step] = []
    artifacts: List[Dict] = []
    final_output: Optional[Dict] = None