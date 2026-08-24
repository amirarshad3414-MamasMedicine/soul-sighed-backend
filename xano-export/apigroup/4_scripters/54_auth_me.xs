// Get the record belonging to the authentication token
query "auth/me" verb=GET {
  api_group = "scripters"
  auth = "user"

  input {
  }

  stack {
    db.get user {
      field_name = "id"
      field_value = $auth.id
      output = [
        "id"
        "created_at"
        "name"
        "email"
        "account_id"
        "relationship_focus"
        "role"
        "password_reset"
      ]
    } as $user
  }

  response = $user
}