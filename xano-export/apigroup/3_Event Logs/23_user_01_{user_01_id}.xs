// Delete User_01 record.
query "user_01/{user_01_id}" verb=DELETE {
  api_group = "Event Logs"

  input {
    uuid user_01_id?
  }

  stack {
    db.del User_01 {
      field_name = "id"
      field_value = $input.user_01_id
    }
  }

  response = null
}