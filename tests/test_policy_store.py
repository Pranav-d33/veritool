import json
import tempfile
from pathlib import Path

import pytest

from policy_store.store import PolicyStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as td:
        yield PolicyStore(Path(td))


class TestPolicyStore:
    def test_empty_store(self, store):
        assert store.policies == {}
        assert store.versions == []

    def test_hot_reload_adds_policy(self, store):
        policy_file = store.store_dir / "test_policy.json"
        policy_file.write_text(json.dumps({"name": "test_policy", "rules": []}))
        result = store.hot_reload(policy_file)
        assert "version" in result
        assert result["active_policies"] == ["test_policy"]

    def test_hot_reload_versions(self, store):
        p1 = store.store_dir / "policy_v1.json"
        p1.write_text(json.dumps({"name": "policy_v1"}))
        r1 = store.hot_reload(p1)

        p2 = store.store_dir / "policy_v2.json"
        p2.write_text(json.dumps({"name": "policy_v2"}))
        r2 = store.hot_reload(p2)

        assert len(store.versions) == 2
        assert r2["version"] != r1["version"]

    def test_hot_reload_deactivates_old(self, store):
        p1 = store.store_dir / "v1.json"
        p1.write_text(json.dumps({"name": "v1"}))
        store.hot_reload(p1)

        p2 = store.store_dir / "v2.json"
        p2.write_text(json.dumps({"name": "v2"}))
        store.hot_reload(p2)

        active = [v for v in store.versions if v.active]
        assert len(active) == 1
        assert active[0].version == store.versions[-1].version

    def test_rollback(self, store):
        p1 = store.store_dir / "v1.json"
        p1.write_text(json.dumps({"name": "v1"}))
        r1 = store.hot_reload(p1)

        p2 = store.store_dir / "v2.json"
        p2.write_text(json.dumps({"name": "v2"}))
        store.hot_reload(p2)

        store.rollback(r1["version"])
        active = [v for v in store.versions if v.active]
        assert len(active) == 1
        assert active[0].version == r1["version"]

    def test_load_restores_active(self, store):
        p1 = store.store_dir / "v1.json"
        p1.write_text(json.dumps({"name": "v1"}))
        store.hot_reload(p1)

        store2 = PolicyStore(store.store_dir)
        store2.load()
        assert "v1" in store2.policies

    def test_get_history(self, store):
        p1 = store.store_dir / "v1.json"
        p1.write_text(json.dumps({"name": "v1"}))
        store.hot_reload(p1)

        p2 = store.store_dir / "v2.json"
        p2.write_text(json.dumps({"name": "v2"}))
        store.hot_reload(p2)

        history = store.get_history()
        assert len(history) == 2

    def test_nonexistent_file_raises(self, store):
        with pytest.raises(FileNotFoundError):
            store.hot_reload(Path("/nonexistent/policy.json"))

    def test_manifest_persists(self, store):
        p1 = store.store_dir / "v1.json"
        p1.write_text(json.dumps({"name": "v1"}))
        store.hot_reload(p1)

        assert store._manifest_path().exists()
        manifest = json.loads(store._manifest_path().read_text())
        assert "versions" in manifest
        assert len(manifest["versions"]) == 1
