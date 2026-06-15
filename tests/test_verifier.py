from verifier.verifier import Verifier
from bridge.invariant import (
    OrderingInvariant, ExclusiveAccessInvariant,
    ApprovalInvariant, MonotonicInvariant,
)


class TestOrderingInvariant:
    def test_permit_when_not_target_action(self):
        v = Verifier()
        v.register_tool("build", action_type="BUILD")
        v.add_invariant(OrderingInvariant("DEPLOY", ["BUILD"]))

        fn = v.wrap(lambda **kw: "ok", tool_name="build")
        result = fn()
        assert result == "ok"

    def test_block_deploy_without_build(self):
        v = Verifier()
        v.register_tool("deploy", action_type="DEPLOY")
        v.add_invariant(OrderingInvariant("DEPLOY", ["BUILD"]))

        fn = v.wrap(lambda **kw: "ok", tool_name="deploy")
        result = fn()
        assert result["status"] == "blocked"
        assert "BUILD" in result["reason"]

    def test_permit_deploy_after_build(self):
        v = Verifier()
        v.register_tool("build", action_type="BUILD")
        v.register_tool("deploy", action_type="DEPLOY")
        v.add_invariant(OrderingInvariant("DEPLOY", ["BUILD"]))

        build = v.wrap(lambda **kw: "built", tool_name="build")
        deploy = v.wrap(lambda **kw: "deployed", tool_name="deploy")

        assert build() == "built"
        assert deploy() == "deployed"

    def test_require_multiple_prereqs(self):
        v = Verifier()
        v.register_tool("build", action_type="BUILD")
        v.register_tool("test", action_type="TEST")
        v.register_tool("approve", action_type="APPROVE")
        v.register_tool("deploy", action_type="DEPLOY")
        v.add_invariant(OrderingInvariant("DEPLOY", ["BUILD", "TEST", "APPROVE"]))

        build = v.wrap(lambda **kw: "built", tool_name="build")
        test = v.wrap(lambda **kw: "tested", tool_name="test")
        approve = v.wrap(lambda **kw: "approved", tool_name="approve")
        deploy = v.wrap(lambda **kw: "deployed", tool_name="deploy")

        assert build() == "built"
        assert test() == "tested"
        assert deploy()["status"] == "blocked"  # missing approve

        assert approve() == "approved"
        assert deploy() == "deployed"


class TestExclusiveAccess:
    def test_concurrent_access_blocked(self):
        v = Verifier()
        v.register_tool("write_db", action_type="WRITE", resource_fn=lambda a: a.get("db"))
        v.add_invariant(ExclusiveAccessInvariant("WRITE"))

        alice = v.wrap(lambda **kw: "ok", tool_name="write_db")
        v.agent_name = "bob"
        bob = v.wrap(lambda **kw: "ok", tool_name="write_db")

        v.agent_name = "alice"
        assert alice(db="payments") == "ok"

        v.agent_name = "bob"
        result = bob(db="payments")
        assert result["status"] == "blocked"

    def test_different_resource_permitted(self):
        v = Verifier()
        v.register_tool("write_db", action_type="WRITE", resource_fn=lambda a: a.get("db"))
        v.add_invariant(ExclusiveAccessInvariant("WRITE"))

        a = v.wrap(lambda **kw: "ok", tool_name="write_db")
        b = v.wrap(lambda **kw: "ok", tool_name="write_db")
        v.agent_name = "alice"
        a(db="db1")
        v.agent_name = "bob"
        result = b(db="db2")
        assert result == "ok"


class TestApproval:
    def test_requires_approval_by_different_agent(self):
        v = Verifier()
        v.register_tool("approve", action_type="APPROVE")
        v.register_tool("deploy", action_type="DEPLOY")
        v.add_invariant(ApprovalInvariant("DEPLOY", "APPROVE"))

        approve = v.wrap(lambda **kw: "ok", tool_name="approve")
        deploy = v.wrap(lambda **kw: "ok", tool_name="deploy")

        v.agent_name = "alice"
        assert approve() == "ok"
        result = deploy()
        assert result["status"] == "blocked"  # same agent

        v.agent_name = "bob"
        assert deploy() == "ok"


class TestMonotonic:
    def test_counter_increase_permitted(self):
        v = Verifier()
        v.register_tool("set", action_type="COUNTER")
        v.add_invariant(MonotonicInvariant("COUNTER"))

        fn = v.wrap(lambda **kw: "ok", tool_name="set")
        v.agent_name = "alice"
        assert fn(value=5) == "ok"
        assert fn(value=10) == "ok"

    def test_counter_decrease_blocked(self):
        v = Verifier()
        v.register_tool("set", action_type="COUNTER")
        v.add_invariant(MonotonicInvariant("COUNTER"))

        fn = v.wrap(lambda **kw: "ok", tool_name="set")
        assert fn(value=10) == "ok"
        result = fn(value=5)
        assert result["status"] == "blocked"
        assert "decreased" in result["reason"]

    def test_reset_clears_state(self):
        v = Verifier()
        v.register_tool("set", action_type="COUNTER")
        v.add_invariant(MonotonicInvariant("COUNTER"))

        fn = v.wrap(lambda **kw: "ok", tool_name="set")
        assert fn(value=10) == "ok"
        result = fn(value=5)
        assert result["status"] == "blocked"

        v.reset()
        assert fn(value=5) == "ok"


class TestGenericWrap:
    def test_wrap_any_function(self):
        v = Verifier()
        v.register_tool("greet", action_type="GREET")

        fn = v.wrap(lambda name: f"hello {name}", tool_name="greet")
        result = fn(name="world")
        assert result == "hello world"

    def test_multiple_tools_same_verifier(self):
        v = Verifier()
        v.register_tool("add", action_type="MATH")
        v.register_tool("mul", action_type="MATH")

        add = v.wrap(lambda a, b: a + b, tool_name="add")
        mul = v.wrap(lambda a, b: a * b, tool_name="mul")

        assert add(a=2, b=3) == 5
        assert mul(a=4, b=5) == 20

    def test_blocked_action_does_not_execute(self):
        v = Verifier()
        v.register_tool("danger", action_type="DANGER")
        v.add_invariant(OrderingInvariant("DANGER", ["SAFETY_CHECK"]))

        called = []

        def dangerous():
            called.append(True)
            return "boom"

        fn = v.wrap(dangerous, tool_name="danger")
        result = fn()
        assert result["status"] == "blocked"
        assert called == []

    def test_unregistered_tool_uses_name_as_type(self):
        v = Verifier()
        v.register_tool("safe", action_type="SAFE")
        v.add_invariant(OrderingInvariant("SAFE", ["INIT"]))

        safe = v.wrap(lambda: "ok", tool_name="safe")
        result = safe()
        assert result["status"] == "blocked"  # INIT not present
