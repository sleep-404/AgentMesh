
package agentmesh

# Allow marketing to query sales KB
allow if {
    input.principal == "marketing-agent-2"
    input.resource == "sales-kb-1"
    input.action == "query"
}

# Define field masks for marketing (PII protection)
field_masks contains mask if {
    input.principal == "marketing-agent-2"
    input.resource == "sales-kb-1"
    mask := "customer_email"
}

field_masks contains mask if {
    input.principal == "marketing-agent-2"
    input.resource == "sales-kb-1"
    mask := "customer_phone"
}

# Deny marketing from writing
deny if {
    input.principal == "marketing-agent-2"
    input.resource == "sales-kb-1"
    input.action == "write"
}
