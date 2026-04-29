# Graph Health Dependency Decision

Date: 2026-04-29

Memory Substrate should not add a graph analysis dependency for the first graph-health report pass.

Current decision:

- Implement `memory_maintain report` graph insights with deterministic local algorithms over the existing graph backend export contract.
- Surface isolated nodes, sparse clusters, bridge nodes, and weakly connected scopes as read-only maintenance signals.
- Do not add `networkx` yet; the current graph-health needs are small, deterministic, and easy to test without an additional dependency.
- Do not add UI-oriented graph libraries such as graphology or sigma to the memory core.
- Re-evaluate `networkx` only if report logic grows into weighted centrality, community detection, path analysis, or large-graph performance requirements.

Rationale:

- The memory core needs agent-actionable diagnostics before visualization.
- Keeping graph insights inside `memory_maintain report` preserves the MCP boundary and avoids a product/UI dependency.
- The current algorithms operate on exported local backend records, so they work for file and Kuzu graph backends through the same contract.
