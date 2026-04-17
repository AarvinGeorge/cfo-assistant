"""
test_orchestrator_modeling.py

Tests that verify the financial modelling and scenario analysis nodes within the LangGraph orchestrator.

Role in project:
    Test suite — verifies the behaviour of financial_model_node and scenario_node in backend.agents.orchestrator. Run with:
    pytest tests/test_orchestrator_modeling.py -v

Coverage:
    - financial_model_node invokes build_dcf_model or build_ratio_scorecard based on the LLM-selected model_type
    - financial_model_node returns an "insufficient_data" result when the LLM signals missing inputs
    - financial_model_node returns an "error" result for unparseable JSON or model execution exceptions
    - scenario_node invokes calculate_cash_runway for runway analyses and run_scenario_matrix for scenario matrices
    - generate_response calls mcp_citation_validator and appends an uncited-claims warning when validation fails
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage
from backend.agents.orchestrator import financial_model_node, scenario_node, generate_response


class TestFinancialModelNodeCallsModels:
    def test_dcf_model_is_executed(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content=json.dumps({
            "model_type": "dcf",
            "parameters": {"revenue": 1000000, "ebit": 150000, "wacc": 0.10, "terminal_growth": 0.03},
            "explanation": "Running DCF"
        }))
        state = {"current_query": "Run a DCF", "formatted_context": "", "intent": "financial_model"}

        with patch("backend.agents.orchestrator.get_llm", return_value=mock_llm), \
             patch("backend.agents.orchestrator.build_dcf_model") as mock_dcf:
            mock_dcf.return_value = {"enterprise_value": 5000000, "projections": []}
            result = financial_model_node(state)

        mock_dcf.assert_called_once()
        assert result["model_output"]["type"] == "dcf"
        assert "enterprise_value" in result["model_output"]["result"]

    def test_ratios_model_is_executed(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content=json.dumps({
            "model_type": "ratios",
            "parameters": {"income_statement": {"revenue": 1000}, "balance_sheet": {"total_assets": 2000}},
            "explanation": "Computing ratios"
        }))
        state = {"current_query": "Show ratios", "formatted_context": "", "intent": "financial_model"}

        with patch("backend.agents.orchestrator.get_llm", return_value=mock_llm), \
             patch("backend.agents.orchestrator.build_ratio_scorecard") as mock_ratios:
            mock_ratios.return_value = {"ratios": {}, "warnings": []}
            result = financial_model_node(state)

        mock_ratios.assert_called_once()

    def test_insufficient_data_no_model_called(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content=json.dumps({
            "model_type": "insufficient_data",
            "missing": ["revenue", "ebit"],
            "explanation": "Need revenue and EBIT"
        }))
        state = {"current_query": "Run DCF", "formatted_context": "", "intent": "financial_model"}

        with patch("backend.agents.orchestrator.get_llm", return_value=mock_llm):
            result = financial_model_node(state)

        assert result["model_output"]["type"] == "insufficient_data"

    def test_unparseable_json_returns_error(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="I can't extract the parameters needed for this model.")
        state = {"current_query": "Run DCF", "formatted_context": "", "intent": "financial_model"}

        with patch("backend.agents.orchestrator.get_llm", return_value=mock_llm):
            result = financial_model_node(state)

        assert result["model_output"]["type"] == "error"

    def test_model_execution_error_handled(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content=json.dumps({
            "model_type": "dcf",
            "parameters": {"bad": "inputs"},
        }))
        state = {"current_query": "Run DCF", "formatted_context": "", "intent": "financial_model"}

        with patch("backend.agents.orchestrator.get_llm", return_value=mock_llm), \
             patch("backend.agents.orchestrator.build_dcf_model", side_effect=KeyError("revenue")):
            result = financial_model_node(state)

        assert result["model_output"]["type"] == "error"


class TestScenarioNodeCallsModels:
    def test_runway_is_executed(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content=json.dumps({
            "analysis_type": "runway",
            "parameters": {"cash_balance": 12000000, "burn_scenarios": [{"name": "Current", "monthly_burn": 500000}]},
        }))
        state = {"current_query": "Cash runway?", "formatted_context": "", "intent": "scenario_analysis"}

        with patch("backend.agents.orchestrator.get_llm", return_value=mock_llm), \
             patch("backend.agents.orchestrator.calculate_cash_runway") as mock_runway:
            mock_runway.return_value = {"scenarios": [{"runway_months": 24}], "critical": False}
            result = scenario_node(state)

        mock_runway.assert_called_once()
        assert result["model_output"]["type"] == "runway"

    def test_scenario_matrix_is_executed(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content=json.dumps({
            "analysis_type": "scenario_matrix",
            "parameters": {"base_inputs": {"revenue": 1000000, "ebit": 150000, "wacc": 0.10, "terminal_growth": 0.03, "revenue_growth": 0.05, "ebit_margin": 0.15, "projection_years": 3}},
        }))
        state = {"current_query": "Run scenarios", "formatted_context": "", "intent": "scenario_analysis"}

        with patch("backend.agents.orchestrator.get_llm", return_value=mock_llm), \
             patch("backend.agents.orchestrator.run_scenario_matrix") as mock_scenarios:
            mock_scenarios.return_value = {"scenarios": {}, "comparison": {}}
            result = scenario_node(state)

        mock_scenarios.assert_called_once()


class TestCitationValidatorWired:
    def test_generate_response_validates_citations(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="Revenue was $10M. [Source: 10-K, revenue, p.5]")
        state = {"current_query": "Revenue?", "intent": "document_qa", "formatted_context": "Context", "model_output": {}}

        with patch("backend.agents.orchestrator.get_llm", return_value=mock_llm), \
             patch("backend.agents.orchestrator.mcp_citation_validator") as mock_validator:
            mock_validator.return_value = {"valid": True, "uncited_claims": 0}
            result = generate_response(state)

        mock_validator.assert_called_once()

    def test_uncited_claims_appends_warning(self):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="Revenue was $10M and costs were $5M.")
        state = {"current_query": "Revenue?", "intent": "document_qa", "formatted_context": "Context", "model_output": {}}

        with patch("backend.agents.orchestrator.get_llm", return_value=mock_llm), \
             patch("backend.agents.orchestrator.mcp_citation_validator") as mock_validator:
            mock_validator.return_value = {"valid": False, "uncited_claims": 2}
            result = generate_response(state)

        assert "\u26a0\ufe0f" in result["response"]
        assert "2 numerical claim(s)" in result["response"]
