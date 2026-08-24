// Add User_01 record
query user_01 verb=POST {
  api_group = "Event Logs"

  input {
    dblink {
      table = "User_01"
    }
  }

  stack {
    db.add User_01 {
      enforce_hidden_fields = false
      data = {created_at: "now"}
    } as $user_01
  }

  response = $user_01
}