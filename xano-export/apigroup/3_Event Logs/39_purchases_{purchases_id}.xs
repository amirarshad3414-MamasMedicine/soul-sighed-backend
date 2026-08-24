// Get Purchases record
query "purchases/{purchases_id}" verb=GET {
  api_group = "Event Logs"

  input {
    uuid purchases_id?
  }

  stack {
    db.get Purchases {
      field_name = "id"
      field_value = $input.purchases_id
    } as $purchases
  
    precondition ($purchases != null) {
      error_type = "notfound"
      error = "Not Found."
    }
  }

  response = $purchases
}