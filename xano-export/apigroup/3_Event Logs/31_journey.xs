// Add Journey record
query journey verb=POST {
  api_group = "Event Logs"

  input {
    dblink {
      table = "Journey"
    }
  }

  stack {
    db.add Journey {
      enforce_hidden_fields = false
      data = {created_at: "now"}
    } as $journey
  }

  response = $journey
}