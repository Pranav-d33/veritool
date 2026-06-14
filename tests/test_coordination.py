import pytest

from verifier.coordination_policy import (
    CoordinationPolicySpec, CoordinationVerifier, Invariant, AgentAction,
)


@pytest.fixture
def basic_spec():
    return CoordinationPolicySpec(
        name="publish_sequence",
        agents=["researcher", "writer", "editor", "publisher"],
        invariants=[
            Invariant("write_before_publish",
                       "published_by(x) → written_by(y) ∧ x ≠ y",
                       "A publish action requires a prior write by a different agent"),
            Invariant("editor_must_approve",
                       "published_by(x) → approved_by(editor, x)",
                       "Publishing requires editor approval"),
            Invariant("no_agent_skips_step",
                       "sequence_order ensures no step is skipped",
                       "Agents must complete in sequence"),
        ],
    )


@pytest.fixture
def verifier(basic_spec):
    return CoordinationVerifier(basic_spec)


class TestCoordinationVerifier:
    def test_permit_valid_sequence(self, verifier):
        r1 = verifier.check_action(AgentAction("researcher", "write_report", {"content": "draft"}, 1.0))
        assert r1["status"] == "permitted"
        r2 = verifier.check_action(AgentAction("editor", "approve_content", {"content_id": 1}, 2.0))
        assert r2["status"] == "permitted"

    def test_block_publish_without_write(self, verifier):
        result = verifier.check_action(AgentAction("publisher", "publish", {"content_id": 1}, 1.0))
        assert result["status"] == "violation"

    def test_block_publish_without_approval(self, verifier):
        verifier.check_action(AgentAction("researcher", "write_report", {}, 1.0))
        result = verifier.check_action(AgentAction("publisher", "publish", {}, 2.0))
        assert result["status"] == "violation"

    def test_permit_publish_after_write_and_approval(self, verifier):
        verifier.check_action(AgentAction("researcher", "write_report", {}, 1.0))
        verifier.check_action(AgentAction("editor", "approve", {}, 2.0))
        result = verifier.check_action(AgentAction("publisher", "publish", {}, 3.0))
        assert result["status"] == "permitted"


class TestCoordinationLocking:
    @pytest.fixture
    def lock_spec(self):
        return CoordinationPolicySpec(
            name="exclusive_locks",
            agents=["agent_a", "agent_b"],
            invariants=[
                Invariant("exclusive_file_access",
                           "exclusive lock invariant",
                           "No two agents can hold the same lock simultaneously"),
            ],
        )

    def test_concurrent_locks_blocked(self, lock_spec):
        v = CoordinationVerifier(lock_spec)
        v.check_action(AgentAction("agent_a", "lock_file", {"target": "file.txt"}, 1.0))
        r = v.check_action(AgentAction("agent_b", "lock_file", {"target": "file.txt"}, 1.1))
        assert r["status"] == "violation"

    def test_release_then_lock_permitted(self, lock_spec):
        v = CoordinationVerifier(lock_spec)
        v.check_action(AgentAction("agent_a", "lock_file", {"target": "file.txt"}, 1.0))
        v.check_action(AgentAction("agent_a", "unlock_file", {"target": "file.txt"}, 2.0))
        r = v.check_action(AgentAction("agent_b", "lock_file", {"target": "file.txt"}, 3.0))
        assert r["status"] == "permitted"


class TestCoordinationMonotonic:
    @pytest.fixture
    def mono_spec(self):
        return CoordinationPolicySpec(
            name="monotonic_counter",
            agents=["agent_a"],
            invariants=[
                Invariant("counter_only_increases",
                           "monotonic counter",
                           "Counter values can only increase"),
            ],
        )

    def test_counter_increase_permitted(self, mono_spec):
        v = CoordinationVerifier(mono_spec)
        r1 = v.check_action(AgentAction("agent_a", "increment", {"counter": "visits", "value": 5}, 1.0))
        assert r1["status"] == "permitted"
        r2 = v.check_action(AgentAction("agent_a", "increment", {"counter": "visits", "value": 10}, 2.0))
        assert r2["status"] == "permitted"

    def test_counter_decrease_blocked(self, mono_spec):
        v = CoordinationVerifier(mono_spec)
        v.check_action(AgentAction("agent_a", "increment", {"counter": "visits", "value": 10}, 1.0))
        r = v.check_action(AgentAction("agent_a", "decrement", {"counter": "visits", "value": 5}, 2.0))
        assert r["status"] == "violation"


class TestCoordinationState:
    def test_get_state(self, verifier):
        verifier.check_action(AgentAction("researcher", "write_report", {}, 1.0))
        state = verifier.get_state()
        assert state["history_count"] == 1
        assert "researcher" in state["agent_states"]

    def test_history_tracks_actions(self, verifier):
        verifier.check_action(AgentAction("a1", "tool1", {}, 1.0))
        verifier.check_action(AgentAction("a2", "tool2", {}, 2.0))
        assert len(verifier.history) == 2

    def test_role_invariant(self):
        spec = CoordinationPolicySpec(
            name="role_test",
            agents=["admin", "user"],
            invariants=[Invariant("role_based_access", "role check", "")],
        )
        v = CoordinationVerifier(spec)
        r = v.check_action(AgentAction("admin", "delete_user", {"role": "admin"}, 1.0))
        assert r["status"] == "violation"


class TestCoordinationEmptySpec:
    def test_empty_spec_permits_all(self):
        spec = CoordinationPolicySpec(name="empty", agents=[], invariants=[])
        v = CoordinationVerifier(spec)
        r = v.check_action(AgentAction("any", "any_tool", {}, 1.0))
        assert r["status"] == "permitted"
