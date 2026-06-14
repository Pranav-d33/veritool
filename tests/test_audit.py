import tempfile
from pathlib import Path

import pytest

from policy_store.audit import AuditTrail, AuditRecord


@pytest.fixture
def audit():
    with tempfile.TemporaryDirectory() as td:
        yield AuditTrail(Path(td))


class TestAuditTrail:
    def test_record_creation(self, audit):
        rec = audit.record(
            tool="confirm_sale",
            args={"model": "Tahoe", "price": 1},
            decision="blocked",
            reason="Below minimum price",
            witness={"price": 1},
            z3_check_ms=3.2,
            lean_theorem="safe_sale",
            policy_version="v1.0.0",
        )
        assert rec.decision == "blocked"
        assert rec.tool == "confirm_sale"
        assert rec.z3_check_ms == 3.2
        assert rec.lean_theorem == "safe_sale"

    def test_multiple_records(self, audit):
        audit.record(tool="confirm_sale", decision="blocked")
        audit.record(tool="confirm_sale", decision="permitted")
        audit.record(tool="delete_file", decision="blocked")
        assert len(audit._records) == 3

    def test_query_by_decision(self, audit):
        audit.record(tool="confirm_sale", decision="blocked")
        audit.record(tool="confirm_sale", decision="permitted")
        audit.record(tool="delete_file", decision="blocked")

        blocked = audit.query(limit=10, decision="blocked")
        assert len(blocked) == 2

        permitted = audit.query(limit=10, decision="permitted")
        assert len(permitted) == 1

    def test_query_by_tool(self, audit):
        audit.record(tool="confirm_sale", decision="blocked")
        audit.record(tool="delete_file", decision="blocked")

        results = audit.query(limit=10, tool="delete_file")
        assert len(results) == 1
        assert results[0].tool == "delete_file"

    def test_query_limit(self, audit):
        for i in range(10):
            audit.record(tool=f"tool_{i}", decision="blocked")

        results = audit.query(limit=3)
        assert len(results) == 3

    def test_get_stats(self, audit):
        audit.record(tool="a", decision="blocked", z3_check_ms=5.0)
        audit.record(tool="b", decision="permitted", z3_check_ms=3.0)
        audit.record(tool="c", decision="blocked", z3_check_ms=2.0)
        audit.record(tool="d", decision="error", z3_check_ms=0.0)

        stats = audit.get_stats()
        assert stats["total"] == 4
        assert stats["blocked"] == 2
        assert stats["permitted"] == 1
        assert stats["errors"] == 1
        assert stats["avg_z3_ms"] == 2.5

    def test_log_file_written(self, audit):
        audit.record(tool="confirm_sale", decision="blocked")
        log_files = list(audit.log_dir.glob("*.jsonl"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "confirm_sale" in content
        assert "blocked" in content

    def test_timestamp_set_automatically(self, audit):
        rec = audit.record(tool="test", decision="permitted")
        assert rec.timestamp > 0

    def test_empty_stats(self, audit):
        stats = audit.get_stats()
        assert stats["total"] == 0
        assert stats["block_rate"] == 0.0

    def test_export_csv(self, audit):
        audit.record(tool="confirm_sale", decision="blocked", z3_check_ms=1.0)
        audit.record(tool="delete_file", decision="permitted", z3_check_ms=2.0)

        csv_path = audit.log_dir / "export.csv"
        audit.export_csv(csv_path)
        assert csv_path.exists()
        content = csv_path.read_text()
        assert "decision" in content
        assert "blocked" in content
        assert "permitted" in content
