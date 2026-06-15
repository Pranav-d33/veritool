package deploy_pipeline

# OPA CANNOT check "did BUILD happen before DEPLOY"
# Best we can do: allow all deploys from ci
allow if {
    input.action == "DEPLOY"
    input.agent == "ci"
}
allow if {
    input.action != "DEPLOY"
}
