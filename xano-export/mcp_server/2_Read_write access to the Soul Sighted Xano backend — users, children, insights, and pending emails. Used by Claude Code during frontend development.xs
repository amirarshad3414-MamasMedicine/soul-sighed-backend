// Read/write access to the Soul Sighted Xano backend — users, children, insights, and pending emails. Used by Claude Code during frontend development
mcp_server "Read/write access to the Soul Sighted Xano backend — users, children, insights, and pending emails. Used by Claude Code during frontend development" {
  canonical = "LyjD2s3s"
  tools = [
    {name: "list_children"}
    {name: "list_insights"}
    {name: "list_pending_emails"}
    {name: "onboarding_stats"}
    {name: "search_xano_docs"}
  ]

  history = 0
}