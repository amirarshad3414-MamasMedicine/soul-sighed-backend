// Query all Insights records
query insights verb=GET {
  api_group = "Event Logs"

  input {
  }

  stack {
    db.query Insights {
      return = {type: "list"}
    } as $insights
  }

  response = $insights
}