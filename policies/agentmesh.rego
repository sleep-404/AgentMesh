package agentmesh

import future.keywords.if
import future.keywords.in

# ============================================
# KB ACCESS POLICIES
# ============================================

# Default deny for KB access
default allow_kb_access = false

# Allow sales agents to read from sales KB
allow_kb_access if {
    input.principal_type == "agent"
    startswith(input.principal_id, "sales-agent-")
    input.resource_type == "kb"
    input.resource_id == "sales-kb-1"
    input.action in ["read", "query", "sql_query"]
}

# Allow marketing agents to read from sales KB
allow_kb_access if {
    input.principal_type == "agent"
    startswith(input.principal_id, "marketing-agent-")
    input.resource_type == "kb"
    input.resource_id == "sales-kb-1"
    input.action in ["read", "query", "sql_query"]
}

# Allow engineering agents to read from engineering KB
allow_kb_access if {
    input.principal_type == "agent"
    startswith(input.principal_id, "engineering-agent-")
    input.resource_type == "kb"
    input.resource_id == "engineering-kb-1"
    input.action in ["read", "query", "cypher_query"]
}

# Allow admin agents full access
allow_kb_access if {
    input.principal_type == "agent"
    startswith(input.principal_id, "admin-agent-")
    input.resource_type == "kb"
}

# ============================================
# AGENT INVOCATION POLICIES
# ============================================

# Default deny for agent invocation
default allow_agent_invoke = false

# Allow sales agents to invoke engineering agents
allow_agent_invoke if {
    input.principal_type == "agent"
    startswith(input.principal_id, "sales-agent-")
    input.resource_type == "agent"
    startswith(input.resource_id, "engineering-agent-")
    input.action == "invoke"
}

# Allow engineering agents to invoke marketing agents
allow_agent_invoke if {
    input.principal_type == "agent"
    startswith(input.principal_id, "engineering-agent-")
    input.resource_type == "agent"
    startswith(input.resource_id, "marketing-agent-")
    input.action == "invoke"
}

# Allow marketing agents to invoke sales agents
allow_agent_invoke if {
    input.principal_type == "agent"
    startswith(input.principal_id, "marketing-agent-")
    input.resource_type == "agent"
    startswith(input.resource_id, "sales-agent-")
    input.action == "invoke"
}

# Allow marketing agents to invoke support agents
allow_agent_invoke if {
    input.principal_type == "agent"
    startswith(input.principal_id, "marketing-agent-")
    input.resource_type == "agent"
    startswith(input.resource_id, "support-agent-")
    input.action == "invoke"
}

# Allow admin agents to invoke any agent
allow_agent_invoke if {
    input.principal_type == "agent"
    startswith(input.principal_id, "admin-agent-")
    input.resource_type == "agent"
    input.action == "invoke"
}

# ============================================
# FIELD-LEVEL MASKING RULES
# ============================================

# Masking rules for sales KB based on requester
# Marketing and sales agents have the same access level
masking_rules = rules if {
    input.principal_type == "agent"
    startswith(input.principal_id, "marketing-agent-")
    input.resource_type == "kb"
    input.resource_id == "sales-kb-1"
    rules := ["ssn", "credit_card"]
}

masking_rules = rules if {
    input.principal_type == "agent"
    startswith(input.principal_id, "sales-agent-")
    input.resource_type == "kb"
    input.resource_id == "sales-kb-1"
    rules := ["ssn", "credit_card"]
}

# No masking for admin agents
masking_rules = [] if {
    input.principal_type == "agent"
    startswith(input.principal_id, "admin-agent-")
}

# Default masking rules (when no specific rule matches)
default masking_rules = ["customer_email", "customer_phone", "ssn", "credit_card", "password"]

# ============================================
# COMBINED DECISION
# ============================================

# Main decision point for KB access
decision = result if {
    input.resource_type == "kb"
    result := {
        "allow": allow_kb_access,
        "masking_rules": masking_rules,
        "reason": reason_kb_access
    }
}

# Main decision point for agent invocation
decision = result if {
    input.resource_type == "agent"
    result := {
        "allow": allow_agent_invoke,
        "masking_rules": [],
        "reason": reason_agent_invoke
    }
}

# Reason for KB access decision
reason_kb_access = msg if {
    allow_kb_access
    msg := "Policy allows KB access"
} else = msg if {
    msg := "No policy grants KB access"
}

# Reason for agent invocation decision
reason_agent_invoke = msg if {
    allow_agent_invoke
    msg := "Policy allows agent invocation"
} else = msg if {
    msg := "No policy grants agent invocation"
}
