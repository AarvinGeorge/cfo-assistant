import pytest
from abc import ABC
from unittest.mock import patch, MagicMock
from backend.agents.base_agent import BaseAgent


class ConcreteAgent(BaseAgent):
    def run(self, query: str, session_id: str) -> str:
        return f"response to: {query}"


def test_base_agent_is_abstract():
    assert issubclass(BaseAgent, ABC)


def test_base_agent_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BaseAgent()


def test_concrete_agent_inherits_client():
    mock_anthropic = MagicMock()
    with patch("backend.agents.base_agent.anthropic.Anthropic", return_value=mock_anthropic):
        agent = ConcreteAgent()
    assert agent.client is mock_anthropic


def test_concrete_agent_uses_config_model():
    with patch("backend.agents.base_agent.anthropic.Anthropic"):
        agent = ConcreteAgent()
    assert agent.model == "claude-sonnet-4-6"
    assert agent.max_tokens == 4096


def test_concrete_agent_run_returns_string():
    with patch("backend.agents.base_agent.anthropic.Anthropic"):
        agent = ConcreteAgent()
    result = agent.run("What is EBITDA?", session_id="test-session")
    assert isinstance(result, str)
    assert result == "response to: What is EBITDA?"


def test_run_is_abstract_on_base():
    assert "run" in BaseAgent.__abstractmethods__
