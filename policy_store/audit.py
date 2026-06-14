import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class AuditRecord:
    timestamp: float = 0.0
    tool: str = ""
    args: dict = field(default_factory=dict)
    decision: str = ""
    reason: Any = ""
    witness: dict = field(default_factory=dict)
    z3_check_ms: float = 0.0
    lean_theorem: str = ""
    policy_version: str = ""
    agent: str = ""


class AuditTrail:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._session_id = f"session_{int(time.time())}"
        self._records: list[AuditRecord] = []

    def record(self, **kwargs) -> AuditRecord:
        rec = AuditRecord(
            timestamp=time.time(),
            **kwargs,
        )
        self._records.append(rec)
        self._append_to_file(rec)
        return rec

    def _append_to_file(self, rec: AuditRecord):
        path = self.log_dir / f"{self._session_id}.jsonl"
        with open(path, "a") as f:
            f.write(json.dumps(asdict(rec)) + "\n")

    def query(self, limit: int = 100, **filters) -> list[AuditRecord]:
        results = list(self._records)
        for key, value in filters.items():
            results = [r for r in results if getattr(r, key, None) == value]
        return results[-limit:]

    def get_stats(self) -> dict:
        total = len(self._records)
        blocked = sum(1 for r in self._records if r.decision == "blocked")
        permitted = sum(1 for r in self._records if r.decision == "permitted")
        errors = sum(1 for r in self._records if r.decision == "error")
        avg_ms = 0.0
        if total > 0:
            avg_ms = sum(r.z3_check_ms for r in self._records) / total
        return {
            "total": total,
            "blocked": blocked,
            "permitted": permitted,
            "errors": errors,
            "avg_z3_ms": round(avg_ms, 2),
            "block_rate": round(blocked / total * 100, 1) if total > 0 else 0.0,
        }

    def export_csv(self, path: Path):
        import csv
        with open(path, "w", newline="") as f:
            if not self._records:
                return
            writer = csv.DictWriter(f, fieldnames=asdict(self._records[0]).keys())
            writer.writeheader()
            for r in self._records:
                row = asdict(r)
                row["reason"] = str(row["reason"])
                row["witness"] = str(row["witness"])
                writer.writerow(row)
