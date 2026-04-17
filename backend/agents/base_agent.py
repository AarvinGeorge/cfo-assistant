"""
base_agent.py

Abstract base class defining the interface that all FinSight agent
implementations must conform to.

Role in project:
    Agent layer — currently unused in the active LangGraph flow (the
    orchestrator uses node functions, not class-based agents). Retained as
    an extension point for future specialised agent implementations that
    need shared lifecycle management.

Main parts:
    - BaseAgent: ABC with abstract methods run() and stream(), plus shared
      helpers for logging and error handling that subclasses can inherit.
"""
from abc import ABC, abstractmethod
import anthropic
from backend.core.config import get_settings


class BaseAgent(ABC):
    def __init__(self):
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.max_tokens = settings.claude_max_tokens

    @abstractmethod
    def run(self, query: str, session_id: str) -> str:
        pass
