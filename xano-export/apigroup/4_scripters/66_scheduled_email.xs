// Creates a new email record to be scheduled
query scheduled_email verb=POST {
  api_group = "scripters"

  input {
    // Recipient email address
    email email
  
    // Subject line of the email
    text subject filters=trim
  
    // HTML content of the email body
    text body filters=trim
  
    // Scheduled time for the email
    timestamp scheduled_time
  }

  stack {
    db.add Email {
      enforce_hidden_fields = false
      data = {
        email       : $input.email
        subject     : $input.subject
        html_content: $input.body
        timestamp   : $input.scheduled_time
        delivered   : false
      }
    } as $new_email
  }

  response = $new_email
}