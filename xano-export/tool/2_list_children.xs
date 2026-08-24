// Lists children records so the coding agent can see real data shapes.
tool list_children {
  instructions = "Returns rows from the `children` table — the child or parent figures a user has added during onboarding. Each row has id (uuid), user_01_id, user_id, name, date_of_birth, time_of_birth, lat, lon, pronoun, default_child and relationship_focus ('child' or 'parent'). Use this to inspect real record shapes before writing frontend code against them."

  input {
  }

  stack {
    db.query children {
      sort = {children.created_at: "desc"}
      return = {type: "list"}
    } as $rows
  }

  response = $rows
}