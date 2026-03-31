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
