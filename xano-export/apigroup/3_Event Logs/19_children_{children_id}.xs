// Get children record
query "children/{children_id}" verb=GET {
  api_group = "Event Logs"

  input {
    int children_id? filters=min:1
  }

  stack {
    db.get "" {
      field_name = "id"
      field_value = $input.children_id
    } as $children
  
    precondition ($children != null) {
      error_type = "notfound"
      error = "Not Found."
    }
  }

  response = $children
}