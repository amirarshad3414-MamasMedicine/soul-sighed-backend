// Marks an email as delivered.
query deliver_email verb=POST {
  api_group = "scripters"

  input {
    // The ID of the email to mark as delivered.
    int email_id
  }

  stack {
    // Fetch the email record from the Email table
    db.get Email {
      field_name = "id"
      field_value = $input.email_id
    } as $email_record
  
    // Ensure the email record exists
    precondition ($email_record != null) {
      error_type = "inputerror"
      error = "Email record not found."
    }
  
    // Update the delivered status and timestamp
    db.edit Email {
      field_name = "id"
      field_value = $input.email_id
      enforce_hidden_fields = false
      data = {delivered: true, timestamp: "now"}
    } as $updated_email
  }

  response = $updated_email
}