// Edit Insights record
query "insights/{insights_id}" verb=PATCH {
  api_group = "Event Logs"

  input {
    uuid insights_id?
    dblink {
      table = "Insights"
    }
  }

  stack {
    util.get_raw_input {
      encoding = "json"
      exclude_middleware = false
    } as $raw_input
  
    db.patch Insights {
      field_name = "id"
      field_value = $input.insights_id
      data = `$input|pick:($raw_input|keys)`|filter_null|filter_empty_text
    } as $insights
  }

  response = $insights
}