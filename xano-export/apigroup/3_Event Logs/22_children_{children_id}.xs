// Edit children record
query "children/{children_id}" verb=PATCH {
  api_group = "Event Logs"

  input {
    int children_id? filters=min:1
  }

  stack {
    util.get_raw_input {
      encoding = "json"
      exclude_middleware = false
    } as $raw_input
  
    db.patch "" {
      field_name = "id"
      field_value = $input.children_id
      data = `$input|pick:($raw_input|keys)`|filter_null|filter_empty_text
    } as $children
  }

  response = $children
}