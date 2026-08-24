// Updates a user's password based on their email address.
query update_password verb=POST {
  api_group = "scripters"

  input {
    // The email address of the user
    text email filters=trim|lower
  
    // The new password for the user
    text newPassword {
      sensitive = true
    }
  }

  stack {
    // Retrieve the user record by email
    db.get user {
      field_name = "email"
      field_value = $input.email
    } as $user
  
    // Check if a user record was found
    precondition ($user != null) {
      error_type = "accessdenied"
      error = "404 Not Found"
    }
  
    // Update the user's password
    db.edit user {
      field_name = "id"
      field_value = $user.id
      enforce_hidden_fields = false
      data = {password: $input.newPassword}
    } as $updated_user
  }

  response = {message: "Password updated successfully"}
}