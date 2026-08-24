// Get User_01 record
query "user_01/{user_01_id}" verb=GET {
  api_group = "Event Logs"

  input {
    uuid user_01_id?
  }

  stack {
    db.get User_01 {
      field_name = "id"
      field_value = $input.user_01_id
    } as $user_01
  
    precondition ($user_01 != null) {
      error_type = "notfound"
      error = "Not Found."
    }
  }

  response = $user_01
}