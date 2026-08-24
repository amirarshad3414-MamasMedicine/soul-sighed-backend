// Delete children record.
query "children/{children_id}" verb=DELETE {
  api_group = "Event Logs"

  input {
    int children_id? filters=min:1
  }

  stack {
    db.del "" {
      field_name = "id"
      field_value = $input.children_id
    }
  }

  response = null
}