// Signup and retrieve an authentication token
// Select the profile subject for the astrology insight. This choice determines whether the generation logic focuses on the 'parent' or 'child' perspective
// Removed from the input object 
// enum relationshipFocus?=parent {
//   values = ["parent", "child"]
// }
query "auth/signup" verb=POST {
  api_group = "scripters"

  input {
    text name?
    email email? filters=lower|trim
    password password?
  }

  stack {
    db.get user {
      field_name = "email"
      field_value = $input.email
    } as $user
  
    precondition ($user == null) {
      error_type = "accessdenied"
      error = "This account is already in use."
    }
  
    db.add user {
      enforce_hidden_fields = false
      data = {
        created_at: "now"
        name      : $input.name
        email     : $input.email
        password  : $input.password
      }
    } as $user
  
    // Remove the below line to add in the record of user
    // "relationship_focus": $input.relationshipFocus
  
    db.add children {
      enforce_hidden_fields = false
      data = {
        created_at   : "now"
        user_id      : $user.id
        default_child: true
      }
    } as $children1
  
    db.query Purchases {
      where = $db.Purchases.email == $input.email
      return = {type: "list"}
    } as $purchases
  
    // Iterate over the found purchases and update each record
    foreach ($purchases) {
      each as $purchase {
        db.edit Purchases {
          field_name = "id"
          field_value = $purchase.id
          enforce_hidden_fields = false
          data = {user_id: $user.id, child_id: $children1.id}
        } as $updated_purchase
      }
    }
  
    security.create_auth_token {
      table = "user"
      extras = {}
      expiration = 86400
      id = $user.id
    } as $authToken
  }

  response = {authToken: $authToken}
}