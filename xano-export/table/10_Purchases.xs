table Purchases {
  auth = false

  schema {
    uuid id
    timestamp created_at?=now {
      visibility = "private"
    }
  
    int? user_id? {
      table = "user"
    }
  
    // References the children table for the child associated with the purchase.
    uuid? child_id? {
      table = "children"
    }
  
    // References the Journey table for the journey associated with the purchase.
    uuid journey_id? {
      table = "Journey"
    }
  
    // The source or platform where the purchase was made.
    text purchase_source? filters=trim
  
    // A unique reference identifier for the purchase.
    text purchase_reference? filters=trim
  
    text? email? filters=trim
  }

  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "created_at", op: "desc"}]}
  ]
}