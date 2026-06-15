from bridge.invariant import (
    OrderingInvariant, ExclusiveAccessInvariant,
    ApprovalInvariant, MonotonicInvariant,
)

scenarios = [
    {
        "name": "deploy_pipeline",
        "invariants": [OrderingInvariant("DEPLOY", ["BUILD", "TEST", "APPROVE"])],
        "opa_limit": "Cannot express 'before DEPLOY, BUILD must have occurred'. OPA evaluates each request independently — no session-level sequence tracking.",
        "cases": [
            {
                "name": "valid_sequence",
                "trace": [
                    ("ci", "build", "BUILD", {}),
                    ("ci", "test", "TEST", {}),
                    ("qa", "approve", "APPROVE", {}),
                    ("ci", "deploy", "DEPLOY", {"env": "prod"}),
                ],
                "expect": "permitted",
            },
            {
                "name": "missing_build",
                "trace": [
                    ("ci", "test", "TEST", {}),
                    ("qa", "approve", "APPROVE", {}),
                    ("ci", "deploy", "DEPLOY", {"env": "prod"}),
                ],
                "expect": "blocked",
            },
            {
                "name": "missing_approve",
                "trace": [
                    ("ci", "build", "BUILD", {}),
                    ("ci", "test", "TEST", {}),
                    ("ci", "deploy", "DEPLOY", {"env": "prod"}),
                ],
                "expect": "blocked",
            },
            {
                "name": "deploy_only",
                "trace": [
                    ("ci", "deploy", "DEPLOY", {"env": "prod"}),
                ],
                "expect": "blocked",
            },
        ],
    },
    {
        "name": "concurrent_writes",
        "invariants": [ExclusiveAccessInvariant("WRITE")],
        "opa_limit": "Cannot track 'who holds this resource'. OPA checks authorization at a point — it has no memory of prior access.",
        "cases": [
            {
                "name": "sequential_same_agent",
                "trace": [
                    ("alice", "write", "WRITE", {"file": "data.txt"}),
                ],
                "expect": "permitted",
            },
            {
                "name": "cross_agent_conflict",
                "trace": [
                    ("alice", "write", "WRITE", {"file": "data.txt"}),
                    ("bob", "write", "WRITE", {"file": "data.txt"}),
                ],
                "expect": "blocked",
            },
            {
                "name": "cross_agent_different_resource",
                "trace": [
                    ("alice", "write", "WRITE", {"file": "a.txt"}),
                    ("bob", "write", "WRITE", {"file": "b.txt"}),
                ],
                "expect": "permitted",
            },
            {
                "name": "same_agent_two_writes",
                "trace": [
                    ("alice", "write", "WRITE", {"file": "data.txt"}),
                    ("alice", "write", "WRITE", {"file": "data.txt"}),
                ],
                "expect": "permitted",
            },
        ],
    },
    {
        "name": "self_approval",
        "invariants": [ApprovalInvariant("DEPLOY", "APPROVE")],
        "opa_limit": "Cannot model 'a prior action by a different agent'. The concept of sequence and agent identity across calls is absent.",
        "cases": [
            {
                "name": "different_agent_approves",
                "trace": [
                    ("qa", "approve_deploy", "APPROVE", {}),
                    ("ci", "deploy", "DEPLOY", {}),
                ],
                "expect": "permitted",
            },
            {
                "name": "self_approval_blocked",
                "trace": [
                    ("ci", "approve_deploy", "APPROVE", {}),
                    ("ci", "deploy", "DEPLOY", {}),
                ],
                "expect": "blocked",
            },
            {
                "name": "no_approval",
                "trace": [
                    ("ci", "deploy", "DEPLOY", {}),
                ],
                "expect": "blocked",
            },
            {
                "name": "approval_after_deploy",
                "trace": [
                    ("ci", "deploy", "DEPLOY", {}),
                    ("qa", "approve_deploy", "APPROVE", {}),
                ],
                "expect": "blocked",
            },
        ],
    },
    {
        "name": "monotonic_budget",
        "invariants": [MonotonicInvariant("SPEND")],
        "opa_limit": "Cannot track monotonic state across calls. OPA has no counter abstraction or session state.",
        "cases": [
            {
                "name": "increasing",
                "trace": [
                    ("alice", "spend", "SPEND", {"value": 10}),
                    ("alice", "spend", "SPEND", {"value": 20}),
                    ("alice", "spend", "SPEND", {"value": 30}),
                ],
                "expect": "permitted",
            },
            {
                "name": "decreasing",
                "trace": [
                    ("alice", "spend", "SPEND", {"value": 30}),
                    ("alice", "spend", "SPEND", {"value": 20}),
                ],
                "expect": "blocked",
            },
            {
                "name": "same_value",
                "trace": [
                    ("alice", "spend", "SPEND", {"value": 25}),
                    ("alice", "spend", "SPEND", {"value": 25}),
                ],
                "expect": "permitted",
            },
            {
                "name": "separate_agents",
                "trace": [
                    ("alice", "spend", "SPEND", {"value": 50}),
                    ("bob", "spend", "SPEND", {"value": 10}),
                ],
                "expect": "permitted",
            },
        ],
    },
    {
        "name": "composite_deploy",
        "invariants": [
            OrderingInvariant("DEPLOY", ["BUILD", "TEST"]),
            ExclusiveAccessInvariant("DEPLOY"),
        ],
        "opa_limit": "Cannot express ordering or exclusivity. A composite of two unsupported checks is doubly unsupported.",
        "cases": [
            {
                "name": "valid_sequence",
                "trace": [
                    ("ci", "build", "BUILD", {}),
                    ("ci", "test", "TEST", {}),
                    ("ci", "deploy", "DEPLOY", {"env": "prod"}),
                ],
                "expect": "permitted",
            },
            {
                "name": "missing_prereq",
                "trace": [
                    ("ci", "deploy", "DEPLOY", {"env": "prod"}),
                ],
                "expect": "blocked",
            },
            {
                "name": "concurrent_deploy",
                "trace": [
                    ("ci", "build", "BUILD", {}),
                    ("ci", "test", "TEST", {}),
                    ("alice", "deploy", "DEPLOY", {"env": "prod"}),
                    ("bob", "deploy", "DEPLOY", {"env": "prod"}),
                ],
                "expect": "blocked",
            },
            {
                "name": "both_violations",
                "trace": [
                    ("bob", "deploy", "DEPLOY", {"env": "prod"}),
                ],
                "expect": "blocked",
            },
        ],
    },
    {
        "name": "empty_trace",
        "invariants": [
            OrderingInvariant("DEPLOY", ["BUILD"]),
            ExclusiveAccessInvariant("WRITE"),
            ApprovalInvariant("DEPLOY", "APPROVE"),
            MonotonicInvariant("SPEND"),
        ],
        "opa_limit": "Base case — vacuously safe in any system, but VeriTool's Lean theorems prove this formally.",
        "cases": [
            {
                "name": "no_actions",
                "trace": [],
                "expect": "permitted",
            },
            {
                "name": "single_unrelated",
                "trace": [
                    ("any", "ping", "PING", {}),
                ],
                "expect": "permitted",
            },
        ],
    },
    {
        "name": "noop_actions",
        "invariants": [
            OrderingInvariant("DEPLOY", ["BUILD"]),
            ExclusiveAccessInvariant("WRITE"),
        ],
        "opa_limit": "Irrelevant actions shouldn't affect results. VeriTool correctly ignores non-matching action types.",
        "cases": [
            {
                "name": "interleaved_noops",
                "trace": [
                    ("ci", "build", "BUILD", {}),
                    ("any", "log", "LOG", {}),
                    ("any", "notify", "NOTIFY", {}),
                    ("ci", "deploy", "DEPLOY", {}),
                ],
                "expect": "permitted",
            },
            {
                "name": "noops_with_violation",
                "trace": [
                    ("any", "log", "LOG", {}),
                    ("ci", "deploy", "DEPLOY", {}),
                ],
                "expect": "blocked",
            },
        ],
    },
]
