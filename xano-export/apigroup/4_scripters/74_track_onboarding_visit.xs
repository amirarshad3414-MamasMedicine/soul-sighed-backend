// Records that a user reached a stage of the /signup-flow onboarding.
query track_onboarding_visit verb=POST {
  api_group = "scripters"

  input {
    // Anonymous per-browser identifier.
    text session_id filters=trim
  
    // "child" or "parent". May be omitted: after the Stripe round-trip the page
    // reloads and the browser no longer knows which flow it was in, so the flow
    // is resolved from this session's earlier rows instead.
    text flow? filters=trim
  
    // Stage key from STEPS in signup-flow/lib.js, e.g. "names".
    text step filters=trim
  
    // Zero-based position of the stage within STEPS.
    int step_index
  }

  stack {
    // Most recent stage this session recorded, in any flow. A session can hold
    // both flows if the visitor went back and switched, so "most recent" is the
    // best available answer to which funnel they were actually in.
    db.query onboarding_visit {
      where = $db.onboarding_visit.session_id == $input.session_id
      sort = {onboarding_visit.created_at: "desc"}
      return = {type: "single"}
    } as $last
  
    var $flow {
      value = $input.flow
    }
  
    conditional {
      if ($input.flow == "" && $last != null) {
        var $flow {
          value = $last.flow
        }
      }
    }
  
    // Nothing to attribute the visit to: the caller gave no flow and this
    // session has no earlier rows to infer one from.
    precondition ($flow != "") {
      error = "Unable to determine the onboarding flow for this session"
    }
  
    // One row per browser per flow per stage.
    db.query onboarding_visit {
      where = $db.onboarding_visit.session_id == $input.session_id && $db.onboarding_visit.flow == $flow && $db.onboarding_visit.step == $input.step
      return = {type: "single"}
    } as $existing
  
    conditional {
      if ($existing != null) {
        var $counted {
          value = false
        }
      }
    
      else {
        db.add onboarding_visit {
          enforce_hidden_fields = false
          data = {
            created_at: "now"
            session_id: $input.session_id
            flow      : $flow
            step      : $input.step
            step_index: $input.step_index
          }
        } as $created
      
        var $counted {
          value = true
        }
      }
    }
  }

  response = {counted: $counted, flow: $flow}
}