// Delete Journey record.
query "journey/{journey_id}" verb=DELETE {
  api_group = "Event Logs"

  input {
    uuid journey_id?
  }

  stack {
    db.del Journey {
      field_name = "id"
      field_value = $input.journey_id
    }
  }

  response = null
}