// Retrieves the dashboard state for a specific child, calculating the status of each journey based on purchases and insights.
query dashboard_state verb=GET {
  api_group = "scripters"

  input {
    // The UUID of the child to retrieve the dashboard state for.
    uuid child_id {
      table = "children"
    }
  }

  stack {
    var $auth_header {
      value = $env.$http_headers|get:"Authorization"
    }
  
    // Call the external validation API and wait for the response
    api.request {
      url = $env.EXTERNAL_VALIDATE_USER_API_URL
      method = "GET"
      headers = []
        |push:"Authorization: " ~ $auth_header
    } as $validation_response
  
    var $api_res {
      value = {
        access : $validation_response.response.result.payload.access
        message: $validation_response.response.result.payload.message
      }
    }
  
    precondition ($validation_response.response.status != 401) {
      error_type = "unauthorized"
      payload = $api_res
    }
  
    precondition ($validation_response.response.status != 404) {
      error_type = "notfound"
      payload = $api_res
    }
  
    precondition ($validation_response.response.status == 200) {
      error_type = "accessdenied"
      payload = $api_res
    }
  
    var $user_id {
      value = $validation_response.response.result.payload.data.id
    }
  
    // Fetch the child details using the provided child_id
    db.get children {
      field_name = "id"
      field_value = $input.child_id
    } as $child
  
    // Ensure the child exists and belongs to the authenticated user
  
    precondition ($child != null && $child.user_01_id == $user_id) {
      error_type = "accessdenied"
      payload = {
        message: "Please enter the valid child id which belog to you"
      }
    }
  
    // Fetch all available journeys
    db.query Journey {
      return = {type: "list"}
    } as $journeys
  
    // Initialize the array to hold the processed journey states
    var $dashboard_journeys {
      value = []
    }
  
    // Iterate through each journey to determine its state for the child
    foreach ($journeys) {
      each as $journey {
        // Check if a purchase exists for this journey, child and logged in user, returning the record to get the ID
        db.query Purchases {
          where = $db.Purchases.user_id == $user_id && $db.Purchases.child_id == $input.child_id && $db.Purchases.journey_id == $journey.id
          return = {type: "single"}
        } as $purchase
      
        // Fetch the insight record if it exists
        db.query Insights {
          where = $db.Insights.user_id == $user_id && $db.Insights.child_id == $input.child_id && $db.Insights.journey_id == $journey.id
          return = {type: "single"}
        } as $insight
      
        // Determine the state based on purchase and insight existence/status
        var $state {
          value = "EXPLORE"
        }
      
        conditional {
          if ($purchase) {
            // Purchase exists
            conditional {
              if ($insight) {
                // Insight exists, check status
                conditional {
                  if ($insight.status == "processing") {
                    var.update $state {
                      value = "PROCESSING"
                    }
                  }
                
                  elseif ($insight.status == "ready") {
                    var.update $state {
                      value = "READY"
                    }
                  }
                
                  elseif ($insight.status == "failed") {
                    var.update $state {
                      value = "FAILED"
                    }
                  }
                
                  else {
                    // Insight exists but status is null or unknown, treat as BEGIN
                    var.update $state {
                      value = "BEGIN"
                    }
                  }
                }
              }
            
              else {
                // Purchase exists but no insight record yet
                var.update $state {
                  value = "BEGIN"
                }
              }
            }
          }
        }
      
        // Construct the base journey object
        var $journey_obj {
          value = {
            journey_id : $journey.id
            title      : $journey.title
            description: $journey.desc
            state      : $state
          }
        }
      
        // Add purchase_id if purchase exists
        conditional {
          if ($purchase) {
            var.update $journey_obj {
              value = $journey_obj|set:"purchase_id":$purchase.id
            }
          }
        }
      
        // Add insight_id and status if insight exists and state is not BEGIN/EXPLORE
        conditional {
          if ($state == "PROCESSING" || $state == "READY" || $state == "FAILED") {
            var.update $journey_obj {
              value = $journey_obj|set:"insight_id":$insight.id
            }
          
            var.update $journey_obj {
              value = $journey_obj|set:"status":$insight.status
            }
          }
        }
      
        // Add specific fields for READY or FAILED states
        conditional {
          if ($state == "READY") {
            var.update $journey_obj {
              value = $journey_obj
                |set:"deep_text":$insight.deep_text
            }
          
            var.update $journey_obj {
              value = $journey_obj
                |set:"summary_text":$insight.summary_text
            }
          }
        
          elseif ($state == "FAILED") {
            var.update $journey_obj {
              value = $journey_obj
                |set:"last_error":$insight.last_error
            }
          }
        }
      
        // Add the processed journey to the list
        array.push $dashboard_journeys {
          value = $journey_obj
        }
      }
    }
  }

  response = {
    child   : ```
      {
        child_id: $child.id
        name: $child.name
        dob: $child.date_of_birth
        lat: $child.lat
        lon: $child.lon
      }
      ```
    journeys: $dashboard_journeys
  }
}