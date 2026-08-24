table Journey {
  auth = false

  schema {
    uuid id
    timestamp created_at?=now {
      visibility = "private"
    }
  
    text title? filters=trim
  
    // The description of the Journey type
    text desc? filters=trim
  
    // The number represents at place in the Order of journey 
    int number?
  
    // Stores the Image of the Journey type
    image? image?
  }

  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "created_at", op: "desc"}]}
  ]
}