// Edit Journey record
query "journey/{journey_id}" verb=PATCH {
  api_group = "Event Logs"

  input {
    uuid journey_id?
    dblink {
      table = "Journey"
    }
  }

  stack {
    util.get_raw_input {
      encoding = "json"
      exclude_middleware = false
    } as $raw_input
  
    db.patch Journey {
      field_name = "id"
      field_value = $input.journey_id
      data = `$input|pick:($raw_input|keys)`|filter_null|filter_empty_text
    } as $journey
  }

  response = $journey
}