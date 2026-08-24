// Delete Purchases record.
query "purchases/{purchases_id}" verb=DELETE {
  api_group = "Event Logs"

  input {
    uuid purchases_id?
  }

  stack {
    db.del Purchases {
      field_name = "id"
      field_value = $input.purchases_id
    }
  }

  response = null
}