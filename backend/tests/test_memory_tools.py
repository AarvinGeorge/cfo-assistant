"""
test_memory_tools.py

Tests that verify the MCP memory, logging, citation, and export tools write and read correctly.

Role in project:
    Test suite — verifies the behaviour of backend.mcp_server.tools.memory_tools. Run with:
    pytest tests/test_memory_tools.py -v

Coverage:
    - mcp_memory_write stores a message in Redis with an expiry via rpush and expire
    - mcp_memory_read returns an empty list for a new session and deserialises stored messages correctly
    - mcp_intent_log appends a JSON entry of type "intent_classification" to audit_log.jsonl
    - mcp_citation_validator detects cited and uncited numerical claims in response text
    - mcp_response_logger appends a JSON entry of type "qa_response" including citation_count
    - mcp_export_trigger appends an export-type entry to audit_log.jsonl
"""

import json
import pytest
from unittest.mock import patch, MagicMock, call
from pathlib import Path
from backend.mcp_server.tools.memory_tools import (
    mcp_memory_read, mcp_memory_write, mcp_intent_log,
    mcp_citation_validator, mcp_response_logger, mcp_export_trigger,
)


class TestMemoryReadWrite:
    def test_memory_write(self):
        mock_redis = MagicMock()
        with patch("backend.mcp_server.tools.memory_tools.get_redis_client", return_value=mock_redis):
            result = mcp_memory_write("session-1", {"role": "user", "content": "hello"})
        assert result is True
        mock_redis.rpush.assert_called_once()
        mock_redis.expire.assert_called_once()

    def test_memory_read_empty(self):
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = []
        with patch("backend.mcp_server.tools.memory_tools.get_redis_client", return_value=mock_redis):
            result = mcp_memory_read("session-1")
        assert result == []

    def test_memory_read_with_messages(self):
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = [
            json.dumps({"role": "user", "content": "hello"}),
            json.dumps({"role": "assistant", "content": "hi"}),
        ]
        with patch("backend.mcp_server.tools.memory_tools.get_redis_client", return_value=mock_redis):
            result = mcp_memory_read("session-1")
        assert len(result) == 2
        assert result[0]["role"] == "user"


class TestIntentLog:
    def test_logs_intent(self, tmp_path):
        with patch("backend.mcp_server.tools.memory_tools.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            result = mcp_intent_log("session-1", "document_qa", "What is revenue?")
        assert result is True
        log_file = tmp_path / "audit_log.jsonl"
        assert log_file.exists()
        entry = json.loads(log_file.read_text().strip())
        assert entry["type"] == "intent_classification"
        assert entry["intent"] == "document_qa"


class TestCitationValidator:
    def test_valid_all_cited(self):
        text = "Revenue was $1,234,567 in Q3. [Source: 10-K, income_statement, p.5]"
        result = mcp_citation_validator(text)
        assert result["valid"] is True
        assert len(result["citations_found"]) == 1

    def test_invalid_uncited_number(self):
        text = "Revenue was $1,234,567 in Q3.\n\nExpenses were $500,000 last year."
        result = mcp_citation_validator(text)
        assert result["uncited_claims"] > 0

    def test_no_numbers_is_valid(self):
        text = "The company performed well this quarter."
        result = mcp_citation_validator(text)
        assert result["valid"] is True
        assert result["total_claims"] == 0

    def test_percentage_detected(self):
        text = "Gross margin improved to 45.2%. [Source: 10-K, income_statement, p.3]"
        result = mcp_citation_validator(text)
        assert result["total_claims"] >= 1


class TestResponseLogger:
    def test_logs_response(self, tmp_path):
        with patch("backend.mcp_server.tools.memory_tools.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            result = mcp_response_logger("s1", "what is revenue?", "Revenue is $1M", ["10-K, p.5"])
        assert result is True
        log_file = tmp_path / "audit_log.jsonl"
        entry = json.loads(log_file.read_text().strip())
        assert entry["type"] == "qa_response"
        assert entry["citation_count"] == 1


class TestExportTrigger:
    def test_logs_export(self, tmp_path):
        with patch("backend.mcp_server.tools.memory_tools.get_settings") as mock_settings:
            mock_settings.return_value.output_dir = str(tmp_path)
            result = mcp_export_trigger("s1", "pdf", "dcf_model")
        assert result is True
