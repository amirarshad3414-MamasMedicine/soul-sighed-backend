// Edit User_01 record
query "user_01/{user_01_id}" verb=PATCH {
  api_group = "Event Logs"

  input {
    uuid user_01_id?
    dblink {
      table = "User_01"
    }
  }

  stack {
    util.get_raw_input {
      encoding = "json"
      exclude_middleware = false
    } as $raw_input
  
    db.patch User_01 {
      field_name = "id"
      field_value = $input.user_01_id
      data = `$input|pick:($raw_input|keys)`|filter_null|filter_empty_text
    } as $user_01
  }

  response = $user_01
}