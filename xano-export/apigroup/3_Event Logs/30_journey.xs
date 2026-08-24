// Query all Journey records
query journey verb=GET {
  api_group = "Event Logs"

  input {
  }

  stack {
    db.query Journey {
      return = {type: "list"}
    } as $journey
  }

  response = $journey
}