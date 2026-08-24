// Delete Insights record.
query "insights/{insights_id}" verb=DELETE {
  api_group = "Event Logs"

  input {
    uuid insights_id?
  }

  stack {
    db.del Insights {
      field_name = "id"
      field_value = $input.insights_id
    }
  }

  response = null
}