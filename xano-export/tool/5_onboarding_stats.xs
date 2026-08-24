// Reports how many users entered each onboarding flow in /signup-flow.
tool onboarding_stats {
  instructions = "Returns how many users entered each onboarding in the /signup-flow funnel: child_users chose 'My child', parent_users chose 'My parent'. Counted from the 'relationship' stage, which every visitor records exactly once per flow, so these are user counts and not row or page-view counts. The onboarding_visit table also holds one row per user per stage reached, so per-stage funnel depth can be derived from it separately."

  input {
  }

  stack {
    db.query onboarding_visit {
      where = $db.onboarding_visit.flow == "child" && $db.onboarding_visit.step == "relationship"
      return = {type: "count"}
    } as $child_users
  
    db.query onboarding_visit {
      where = $db.onboarding_visit.flow == "parent" && $db.onboarding_visit.step == "relationship"
      return = {type: "count"}
    } as $parent_users
  }

  response = {child_users: $child_users, parent_users: $parent_users}
}