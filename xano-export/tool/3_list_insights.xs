// Lists insight records, which the frontend renders on the dashboard.
tool list_insights {
  instructions = "Returns rows from the `Insights` table. Each row has id (uuid), real_user_id, child_id, journey_id, status ('processing', 'ready' or 'failed'), deep_text, summary_text, teaser_text, request_id, last_error and insights_api_payload. Use this to inspect insight shape and to check whether generation succeeded or failed for a given user."

  input {
  }

  stack {
    db.query Insights {
      sort = {Insights.created_at: "desc"}
      return = {type: "list"}
    } as $rows
  }

  response = $rows
}