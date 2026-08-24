// Onboarding funnel data for the /signup-flow marketing funnel.
query onboarding_visit_stats verb=GET {
  api_group = "scripters"

  input {
  }

  stack {
    // Users, not rows. Every visitor records the "relationship" stage exactly
    // once per flow, so counting that stage counts people — whereas counting
    // every row would multiply each person by the stages they reached.
    db.query onboarding_visit {
      where = $db.onboarding_visit.flow == "child" && $db.onboarding_visit.step == "relationship"
      return = {type: "count"}
    } as $child_users
  
    db.query onboarding_visit {
      where = $db.onboarding_visit.flow == "parent" && $db.onboarding_visit.step == "relationship"
      return = {type: "count"}
    } as $parent_users
  
    // Every row, for per-stage funnel breakdowns. One row per session per flow
    // per stage, so a stage's row count is already a user count.
    db.query onboarding_visit {
      sort = {onboarding_visit.step_index: "asc"}
      return = {type: "list"}
    } as $rows
  }

  response = {
    child_users : $child_users
    parent_users: $parent_users
    rows        : $rows
  }
}