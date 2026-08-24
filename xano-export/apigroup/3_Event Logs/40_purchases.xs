// Query all Purchases records
query purchases verb=GET {
  api_group = "Event Logs"

  input {
  }

  stack {
    db.query Purchases {
      return = {type: "list"}
    } as $purchases
  }

  response = $purchases
}