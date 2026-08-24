// Fetches children for the authenticated user using an external validation API.
query get_children verb=GET {
  api_group = "scripters"
  auth = "user"

  input {
  }

  stack {
    db.get user {
      field_name = "id"
      field_value = $auth.id
      output = [
        "id"
        "created_at"
        "name"
        "email"
        "account_id"
        "role"
        "password_reset"
      ]
    } as $user
  
    var $user_id {
      value = $user.id
    }
  
    // Query the children table using the user_id
    db.query children {
      where = $db.children.user_id == $user_id
      return = {type: "list"}
    } as $children
  
    db.query Insights {
      where = $db.Insights.real_user_id == $user_id
      return = {type: "list"}
    } as $insights
  
    db.query Purchases {
      where = $db.Purchases.user_id == $user_id
      return = {type: "list"}
    } as $purchases
  }

  response = {
    children : $children
    insights : $insights
    purchases: $purchases
  }
}