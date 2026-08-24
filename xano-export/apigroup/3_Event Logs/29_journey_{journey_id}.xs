// Get Journey record
query "journey/{journey_id}" verb=GET {
  api_group = "Event Logs"

  input {
    uuid journey_id?
  }

  stack {
    db.get Journey {
      field_name = "id"
      field_value = $input.journey_id
    } as $journey
  
    precondition ($journey != null) {
      error_type = "notfound"
      error = "Not Found."
    }
  }

  response = $journey
}