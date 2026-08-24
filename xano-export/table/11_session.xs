table session {
  auth = false

  schema {
    int id
    timestamp created_at?=now {
      visibility = "private"
    }
  
    text session_id? filters=trim
    text customer_id? filters=trim
    int amount_subtotal?
    int amount_total?
    text payment_intent_id? filters=trim
    text payment_status? filters=trim
  }

  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "created_at", op: "desc"}]}
  ]
}