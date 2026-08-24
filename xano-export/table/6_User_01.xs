table User_01 {
  auth = false

  schema {
    uuid id
    timestamp created_at?=now {
      visibility = "private"
    }
  
    // The name of the user.
    text name? filters=trim
  
    // External ID from Memberstack.
    text memberstack_id? filters=trim
  
    // The email address of the user.
    email email? filters=trim|lower
  
    // The user password.
    password password?
  
    // Date of birth of the user.
    date date_of_birth?
  
    // Time of birth of the user.
    timestamp time_of_birth?
  
    // Latitude of birth place.
    decimal lat?
  
    // Longitude of birth place.
    decimal lon?
  
    text pronoun? filters=trim
  }

  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "created_at", op: "desc"}]}
    {
      type : "btree|unique"
      field: [{name: "memberstack_id", op: "asc"}]
    }
    {type: "btree|unique", field: [{name: "email", op: "asc"}]}
  ]
}