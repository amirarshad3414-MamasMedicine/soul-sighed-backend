// Get Insights record
query "insights/{insights_id}" verb=GET {
  api_group = "Event Logs"

  input {
    uuid insights_id?
  }

  stack {
    db.get Insights {
      field_name = "id"
      field_value = $input.insights_id
    } as $insights
  
    precondition ($insights != null) {
      error_type = "notfound"
      error = "Not Found."
    }
  }

  response = $insights
}