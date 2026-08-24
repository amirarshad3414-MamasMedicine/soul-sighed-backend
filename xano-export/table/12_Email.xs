// Stores data for outgoing emails, their content, and delivery status.
table Email {
  auth = false

  schema {
    int id
    timestamp created_at?=now {
      visibility = "private"
    }
  
    // Recipient email address.
    text email? filters=trim
  
    // Subject line of the email.
    text subject? filters=trim
  
    // HTML content of the email body.
    text html_content? filters=trim
  
    // Timestamp when the email was created or sent.
    timestamp timestamp?
  
    // Indicates whether the email has been successfully delivered. Defaults to false.
    bool delivered?
  }

  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "created_at", op: "desc"}]}
  ]
}