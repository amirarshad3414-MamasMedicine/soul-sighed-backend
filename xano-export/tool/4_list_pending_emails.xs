// Lists queued emails the cron job in app/api/cron/route.js drains.
tool list_pending_emails {
  instructions = "Returns rows from the `Email` table that have not been delivered yet (delivered = false), oldest first. Each row has id, email, subject, html_content, timestamp and delivered. This is the same queue the Next.js cron route drains via get_pending_emails / deliver_email."

  input {
  }

  stack {
    db.query Email {
      where = $db.Email.delivered == false
      sort = {Email.timestamp: "asc"}
      return = {type: "list"}
    } as $rows
  }

  response = $rows
}