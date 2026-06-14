import pytest

from verifier.schema import validate_tool_call, ValidationError, SCHEMAS


class TestSchemaConfirmSale:
    def test_valid_minimal(self):
        result = validate_tool_call("confirm_sale", {"model": "Tahoe", "price": 45000, "customer": "Bob"})
        assert result["model"] == "Tahoe"
        assert result["price"] == 45000
        assert result["customer"] == "Bob"

    def test_rejects_unknown_model(self):
        with pytest.raises(ValidationError, match="not valid"):
            validate_tool_call("confirm_sale", {"model": "2024 Tahoe", "price": 1, "customer": "Bob"})

    def test_rejects_model_typo(self):
        with pytest.raises(ValidationError, match="not valid"):
            validate_tool_call("confirm_sale", {"model": "Taho", "price": 1, "customer": "Bob"})

    def test_rejects_lowercase_model(self):
        with pytest.raises(ValidationError, match="not valid"):
            validate_tool_call("confirm_sale", {"model": "tahoe", "price": 1, "customer": "Bob"})

    def test_rejects_arbitrary_model_alias(self):
        with pytest.raises(ValidationError, match="not valid"):
            validate_tool_call("confirm_sale", {"model": "T", "price": 1, "customer": "Bob"})

    def test_coerces_string_price_to_int(self):
        result = validate_tool_call("confirm_sale", {"model": "Tahoe", "price": "45000", "customer": "Alice"})
        assert result["price"] == 45000
        assert isinstance(result["price"], int)

    def test_coerces_float_price_string_to_int(self):
        result = validate_tool_call("confirm_sale", {"model": "Malibu", "price": "25000.0", "customer": "Alice"})
        assert result["price"] == 25000

    def test_accepts_malibu(self):
        result = validate_tool_call("confirm_sale", {"model": "Malibu", "price": 25000, "customer": "Alice"})
        assert result["model"] == "Malibu"

    def test_missing_required_price(self):
        with pytest.raises(ValidationError, match="Missing.*price"):
            validate_tool_call("confirm_sale", {"model": "Tahoe", "customer": "Bob"})

    def test_optional_customer_allowed_missing(self):
        result = validate_tool_call("confirm_sale", {"model": "Tahoe", "price": 1})
        assert result["model"] == "Tahoe"
        assert result["price"] == 1

    def test_rejects_non_int_price(self):
        with pytest.raises(ValidationError, match="int"):
            validate_tool_call("confirm_sale", {"model": "Tahoe", "price": "not_a_number", "customer": "Bob"})


class TestSchemaDeleteFile:
    def test_valid_target(self):
        result = validate_tool_call("delete_file", {"target": "/etc/passwd"})
        assert result["target"] == "/etc/passwd"

    def test_missing_target(self):
        with pytest.raises(ValidationError, match="Missing.*target"):
            validate_tool_call("delete_file", {})


class TestSchemaUnknownTool:
    def test_unknown_tool(self):
        with pytest.raises(ValidationError, match="No schema registered"):
            validate_tool_call("unknown_tool", {})
