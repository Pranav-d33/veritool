import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from verifier.verifier import Verifier


@dataclass
class PolicyVersion:
    version: str
    timestamp: float
    policy_file: str
    checksum: str
    active: bool = False


class PolicyStore:
    def __init__(self, store_dir: Path):
        self.store_dir = store_dir
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.versions_dir = store_dir / "versions"
        self.versions_dir.mkdir(exist_ok=True)
        self.policies: dict[str, Any] = {}
        self.versions: list[PolicyVersion] = []
        self._load_manifest()

    def _manifest_path(self) -> Path:
        return self.store_dir / "manifest.json"

    def _load_manifest(self):
        path = self._manifest_path()
        if path.exists():
            data = json.loads(path.read_text())
            self.versions = [PolicyVersion(**v) for v in data.get("versions", [])]
        else:
            self.versions = []
            self._save_manifest()

    def _save_manifest(self):
        data = {
            "versions": [
                {"version": v.version, "timestamp": v.timestamp,
                 "policy_file": v.policy_file, "checksum": v.checksum,
                 "active": v.active}
                for v in self.versions
            ]
        }
        self._manifest_path().write_text(json.dumps(data, indent=2))

    def load(self):
        for v in self.versions:
            if v.active:
                vpath = self.versions_dir / v.policy_file
                if vpath.exists():
                    self._load_policy_file(vpath)
        return self.policies

    def _load_policy_file(self, path: Path):
        import importlib.util
        data = json.loads(path.read_text()) if path.suffix == ".json" else {}
        if isinstance(data, dict) and "name" in data:
            self.policies[data["name"]] = data

    def hot_reload(self, policy_file: Path) -> dict:
        if not policy_file.exists():
            raise FileNotFoundError(f"Policy file not found: {policy_file}")

        import hashlib
        content = policy_file.read_text()
        checksum = hashlib.sha256(content.encode()).hexdigest()[:12]
        version = f"v{len(self.versions) + 1}.{int(time.time())}"

        for v in self.versions:
            v.active = False

        dest = self.versions_dir / f"{version}_{policy_file.name}"
        shutil.copy2(policy_file, dest)

        pv = PolicyVersion(
            version=version,
            timestamp=time.time(),
            policy_file=dest.name,
            checksum=checksum,
            active=True,
        )
        self.versions.append(pv)
        self._save_manifest()
        self._load_policy_file(dest)

        return {
            "version": version,
            "checksum": checksum,
            "active_policies": list(self.policies.keys()),
        }

    def rollback(self, target_version: str) -> dict:
        for v in self.versions:
            v.active = v.version == target_version

        self._save_manifest()
        self.policies.clear()
        self.load()

        return {
            "rolled_back_to": target_version,
            "active_policies": list(self.policies.keys()),
        }

    def get_history(self) -> list[dict]:
        return [
            {
                "version": v.version,
                "timestamp": v.timestamp,
                "active": v.active,
            }
            for v in sorted(self.versions, key=lambda x: x.timestamp, reverse=True)
        ]
