// Retrieve pending emails to be sent based on current time.
query get_pending_emails verb=GET {
  api_group = "scripters"

  input {
    // The current time to filter scheduled emails up to.
    timestamp current_time
  }

  stack {
    // Retrieve emails that have not been delivered and are scheduled on or before the current time.
    // where = $db.Email.delivered == false && $db.Email.timestamp <= $input.current_time
    // where = $db.Email.delivered == false
  
    db.query Email {
      where = $db.Email.delivered == false && $db.Email.timestamp <= $input.current_time
      sort = {Email.timestamp: "asc"}
      return = {type: "list"}
    } as $pending_emails
  }

  response = $pending_emails
}