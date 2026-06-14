import json
from unittest.mock import Mock, patch

import pytest

from llm.groq_client import _extract_tool_call, GroqClientError


class TestExtractToolCall:
    def test_extract_plain_json(self):
        raw = '{"tool": "confirm_sale", "args": {"model": "Tahoe", "price": 1}}'
        result = _extract_tool_call(raw)
        assert result["tool"] == "confirm_sale"
        assert result["args"]["price"] == 1

    def test_extract_from_code_block(self):
        raw = """```json
{"tool": "confirm_sale", "args": {"model": "Tahoe", "price": 50000}}
```"""
        result = _extract_tool_call(raw)
        assert result["tool"] == "confirm_sale"
        assert result["args"]["price"] == 50000

    def test_extract_from_code_block_no_lang(self):
        raw = """```
{"tool": "delete_file", "args": {"target": "/etc/passwd"}}
```"""
        result = _extract_tool_call(raw)
        assert result["tool"] == "delete_file"

    def test_extract_malformed_json_raises(self):
        with pytest.raises(GroqClientError, match="Could not parse"):
            _extract_tool_call("not json at all")

    def test_extract_empty_string_raises(self):
        with pytest.raises(GroqClientError):
            _extract_tool_call("")

    def test_extract_with_whitespace(self):
        raw = '  \n  {"tool": "confirm_sale", "args": {}}  \n'
        result = _extract_tool_call(raw)
        assert result["tool"] == "confirm_sale"


class TestGroqClientSendPrompt:
    def test_send_prompt_mocked(self):
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content='{"tool": "confirm_sale", "args": {}}'))
        ]

        with patch("llm.groq_client.GroqClient") as MockGroq:
            MockGroq.return_value.chat.completions.create.return_value = mock_response
            with patch("llm.groq_client.GROQ_API_KEY", "test-key"):
                with patch("llm.groq_client.HAS_GROQ", True):
                    from llm.groq_client import send_prompt
                    result = send_prompt("system", "user")
                    assert result["tool"] == "confirm_sale"

    def test_missing_api_key(self):
        with patch("llm.groq_client.GROQ_API_KEY", None):
            with patch("llm.groq_client.HAS_GROQ", True):
                from llm.groq_client import send_prompt
                with pytest.raises(GroqClientError, match="GROQ_API_KEY"):
                    send_prompt("system", "user")

    def test_missing_groq_package(self):
        with patch("llm.groq_client.HAS_GROQ", False):
            from llm.groq_client import send_prompt
            with pytest.raises(GroqClientError, match="groq package"):
                send_prompt("system", "user")

    def test_empty_response_raises(self):
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=None))]

        with patch("llm.groq_client.GroqClient") as MockGroq:
            MockGroq.return_value.chat.completions.create.return_value = mock_response
            with patch("llm.groq_client.GROQ_API_KEY", "test-key"):
                with patch("llm.groq_client.HAS_GROQ", True):
                    from llm.groq_client import send_prompt
                    with pytest.raises(GroqClientError, match="Empty response"):
                        send_prompt("system", "user")
