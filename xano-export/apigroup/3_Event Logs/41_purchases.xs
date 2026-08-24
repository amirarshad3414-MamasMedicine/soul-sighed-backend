// Add Purchases record
query purchases verb=POST {
  api_group = "Event Logs"

  input {
    dblink {
      table = "Purchases"
    }
  }

  stack {
    db.add Purchases {
      enforce_hidden_fields = false
      data = {created_at: "now"}
    } as $purchases
  }

  response = $purchases
}