package veritool_comparison

# === Helper: any action in history matching predicate ===

build_in_history if {
    some a in input.history
    a.action == "BUILD"
}

test_in_history if {
    some a in input.history
    a.action == "TEST"
}

approve_by_other_agent if {
    some a in input.history
    a.action == "APPROVE"
    a.agent != input.agent
}

conflicting_write if {
    some a in input.history
    a.action == "WRITE"
    a.resource == input.resource
    a.agent != input.agent
}

conflicting_deploy if {
    some a in input.history
    a.action == "DEPLOY"
    a.resource == input.resource
    a.agent != input.agent
}

higher_prior_spend if {
    some a in input.history
    a.action == "SPEND"
    a.value > input.value
}

# === Invariant rules ===

order_satisfied if { build_in_history }
order_satisfied if { input.action != "DEPLOY" }

approval_satisfied if { approve_by_other_agent }
approval_satisfied if { input.action != "DEPLOY" }

exclusive_write_ok if { not conflicting_write }
exclusive_write_ok if { input.action != "WRITE" }

exclusive_deploy_ok if { not conflicting_deploy }
exclusive_deploy_ok if { input.action != "DEPLOY" }

monotonic_ok if { not higher_prior_spend }
monotonic_ok if { input.action != "SPEND" }

# === Allow decision ===

allow if {
    order_satisfied
    approval_satisfied
    exclusive_write_ok
    exclusive_deploy_ok
    monotonic_ok
}
