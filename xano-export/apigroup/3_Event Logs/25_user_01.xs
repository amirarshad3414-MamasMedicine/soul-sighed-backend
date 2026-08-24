// Query all User_01 records
query user_01 verb=GET {
  api_group = "Event Logs"

  input {
  }

  stack {
    db.query User_01 {
      return = {type: "list"}
    } as $user_01
  }

  response = $user_01
}