// Edit Purchases record
query "purchases/{purchases_id}" verb=PATCH {
  api_group = "Event Logs"

  input {
    uuid purchases_id?
    dblink {
      table = "Purchases"
    }
  }

  stack {
    util.get_raw_input {
      encoding = "json"
      exclude_middleware = false
    } as $raw_input
  
    db.patch Purchases {
      field_name = "id"
      field_value = $input.purchases_id
      data = `$input|pick:($raw_input|keys)`|filter_null|filter_empty_text
    } as $purchases
  }

  response = $purchases
}