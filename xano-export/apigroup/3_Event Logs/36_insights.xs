// Add Insights record
query insights verb=POST {
  api_group = "Event Logs"

  input {
    dblink {
      table = "Insights"
    }
  }

  stack {
    db.add Insights {
      enforce_hidden_fields = false
      data = {created_at: "now"}
    } as $insights
  }

  response = $insights
}