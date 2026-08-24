// Add children record
query children verb=POST {
  api_group = "Event Logs"

  input {
  }

  stack {
    db.add "" {
      enforce_hidden_fields = false
      data = {created_at: "now"}
    } as $children
  }

  response = $children
}