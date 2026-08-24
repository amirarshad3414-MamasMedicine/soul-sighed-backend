table onboarding_visit {
  auth = false

  schema {
    int id
    timestamp created_at
    text session_id
    text flow
    text step
    int step_index
  }

  index = [
    {type: "primary", field: [{name: "id"}]}
    {
      type : "btree|unique"
      field: [
        {name: "session_id", op: "asc"}
        {name: "flow", op: "asc"}
        {name: "step", op: "asc"}
      ]
    }
  ]
}