// Starts insight generation. Confirms purchase, creates insight record with unique request_id, triggers external API with retries, and updates status.
query submit_onboarding verb=POST {
  api_group = "scripters"
  auth = "user"

  input {
    uuid child_id {
      table = "children"
    }
  
    uuid journey_id {
      table = "Journey"
    }
  
    object onboarding_payload {
      schema {
        text username
        text childname
        timestamp user_dob
        timestamp user_time_of_birth?
        text user_birth_place_id
        timestamp child_dob
        timestamp child_time_of_birth?
        text child_birth_place_id
        text raw_user_message?
        text climate?
        text activation?
        text closeness?
        text posture?
        text summary?
        text emotionTags?
        text keyThemes?
        text parentPronouns?
        text childPronouns?
      }
    }
  
    // This filed tell that user is a child (who wants insight generated for parent) or parent (who wants insight generated for child).
    // The front end collects the info of person_relation user adds to generate the insight. But backend expects the user_realtion so while preparing paylaod we made the user_relation filed and swap the person_relaiton value in it. If the person user added is child then user_relation to him would be "parent"
    text user_relation?=parent filters=trim
  }

  stack {
    var $auth_header {
      value = $env.$http_headers|get:"Authorization"
    }
  
    // // is child check to confirn that user is child or not
    var $is_child {
      value = ($input.user_relation == "child")
    }
  
    // Call the external validation API and wait for the response
    // api.request {
    //   url = $env.EXTERNAL_VALIDATE_USER_API_URL
    //   method = "GET"
    //   headers = []
    //     |push:"Authorization: " ~ $auth_header
    // } as $validation_response
  
    // var $api_res {
    //   value = {
    //     access : $validation_response.response.result.payload.access
    //     message: $validation_response.response.result.payload.message
    //   }
    // }
  
    // precondition ($validation_response.response.status != 401) {
    //   error_type = "unauthorized"
    //   payload = $api_res
    // }
  
    // precondition ($validation_response.response.status != 404) {
    //   error_type = "notfound"
    //   payload = $api_res
    // }
  
    // precondition ($validation_response.response.status == 200) {
    //   error_type = "accessdenied"
    //   payload = $api_res
    // }
  
    db.get user {
      field_name = "id"
      field_value = $auth.id
      output = [
        "id"
        "created_at"
        "name"
        "email"
        "account_id"
        "role"
        "password_reset"
      ]
    } as $user
  
    var $user_id {
      value = $user.id
    }
  
    // Check for existing purchase
    db.query Purchases {
      where = $db.Purchases.user_id == $user_id && $db.Purchases.child_id == $input.child_id && $db.Purchases.journey_id == $input.journey_id
      return = {type: "exists"}
    } as $has_purchase
  
    // precondition ($has_purchase) {
    //   error_type = "accessdenied"
    //   error = "No purchase found for this journey and child."
    // }
  
    // Check for existing active insight
    db.query Insights {
      where = $db.Insights.real_user_id == $user_id && $db.Insights.child_id == $input.child_id && $db.Insights.journey_id == $input.journey_id && ($db.Insights.status == "processing" || $db.Insights.status == "ready")
      return = {type: "single"}
    } as $existing_insight
  
    // conditional {
    //   if ($existing_insight) {
    //     return {
    //       value = {
    //         message   : "Insight already exists."
    //         insight_id: $existing_insight.id
    //         status    : $existing_insight.status
    //       }
    //     }
    //   }
    // }
  
    // Prepare list of locations to geocode
    var $places_to_geocode {
      value = [
        {
          key: "parent"
          place_id: $input.onboarding_payload.user_birth_place_id
        },
        {
          key: "child"
          place_id: $input.onboarding_payload.child_birth_place_id
        }
      ]
    }
  
    var $geocoding_results {
      value = {}
    }
  
    // Loop through locations to geocode
    foreach ($places_to_geocode) {
      each as $place {
        try_catch {
          try {
            api.request {
              url = "https://maps.googleapis.com/maps/api/place/details/json"
              method = "GET"
              params = {
                place_id: $place.place_id
                fields  : "formatted_address,geometry,address_components"
                key     : $env.GOOGLE_PLACES_AUTOCOMPLETE_API_KEY
              }
            } as $geo_response
          
            var $lat {
              value = $geo_response.response.result.result.geometry.location.lat
            }
          
            var $lon {
              value = $geo_response.response.result.result.geometry.location.lng
            }
          
            var.update $geocoding_results {
              value = $geocoding_results
                |set:$place.key:```
                  {
                    lat: $lat
                    lon: $lon
                  }
                  ```
            }
          }
        
          catch {
            // Return error if place resolution fails
            return {
              value = {
                error  : "PLACE_NOT_RESOLVED"
                message: "We couldn’t validate this birthplace. Please select a suggested location from the dropdown."
              }
            }
          }
        }
      }
    }
  
    // Extract results into named variables
    var $parent_birth_place_coordinate {
      value = $geocoding_results.parent
    }
  
    var $child_birth_place_coordinate {
      value = $geocoding_results.child
    }
  
    // Create string variables for Lat/Lon using to_text
    var $parent_lat_string {
      value = $parent_birth_place_coordinate.lat|to_text
    }
  
    var $parent_lon_string {
      value = $parent_birth_place_coordinate.lon|to_text
    }
  
    var $child_lat_string {
      value = $child_birth_place_coordinate.lat|to_text
    }
  
    var $child_lon_string {
      value = $child_birth_place_coordinate.lon|to_text
    }
  
    // // // We moved the creation of child before the preparing the external_api_payload. Now user can genereate insight for parents as well. In that case we need to store the user in the user table but user info in p2 of external api paylaod. For that first we are creating the child (that would be the info of user parent. children table has both child record (in case user is parent) and user parent record (in case user is child))
  
    // Update the children table with the child's birth coordinates
    db.edit children {
      field_name = "id"
      field_value = $input.child_id
      enforce_hidden_fields = false
      data = {
        default_child: false
        name         : $input.onboarding_payload.childname
        lat          : $child_birth_place_coordinate.lat
        lon          : $child_birth_place_coordinate.lon
      }
    } as $updated_child
  
    // // Construct External API Payload explicitly ensuring p1Lat and p2Lat are present
    // var $external_api_payload {
    //   value = ```
    //     {
    //       parentName      : $input.onboarding_payload.username
    //       p1Lat           : $parent_lat_string
    //       p1Lon           : $parent_lon_string
    //       p2Lat           : $child_lat_string
    //       p2Lon           : $child_lon_string
    //       x               : 1
    //       p1Birthday      : $input.onboarding_payload.user_dob
    //       p2Birthday      : $input.onboarding_payload.child_dob
    //       childPronouns   : $input.onboarding_payload.childPronouns|first_notempty:"she/her"
    //       childName       : $input.onboarding_payload.childname
    //       parentPronouns  : $input.onboarding_payload.parentPronouns|first_notempty:"she/her"
    //       rawParentMessage: $input.onboarding_payload.raw_user_message
    //       person_1        : {
    //         birthday: ($input.onboarding_payload.user_dob|format_timestamp:"Y-m-d\\TH:i")
    //         lat: $parent_birth_place_coordinate.lat
    //         lon: $parent_birth_place_coordinate.lon
    //       }
    //       person_2        : {
    //         birthday: ($input.onboarding_payload.child_dob|format_timestamp:"Y-m-d\\TH:i")
    //         lat: $child_birth_place_coordinate.lat
    //         lon: $child_birth_place_coordinate.lon
    //       }
    //       tone_inputs     : {
    //         q1_climate: $input.onboarding_payload.climate
    //         q2_activation: $input.onboarding_payload.activation
    //         q3_closeness: $input.onboarding_payload.closeness
    //         q4_posture: $input.onboarding_payload.posture
    //       }
    //     }
    //     ```
    // }
  
    var $external_api_payload {
      value = {}
    }
  
    // --- Core fields
    var.update $external_api_payload {
      value = $external_api_payload
        |set:"parentName":($is_child ? $input.onboarding_payload.childname : $input.onboarding_payload.username)
        |set:"childName":($is_child ? $input.onboarding_payload.username : $input.onboarding_payload.childname)
        |set:"childPronouns":($is_child ? ($input.onboarding_payload.parentPronouns|first_notempty:"she/her") : ($input.onboarding_payload.childPronouns|first_notempty:"she/her"))
        |set:"parentPronouns":($is_child ? ($input.onboarding_payload.childPronouns|first_notempty:"she/her") : ($input.onboarding_payload.parentPronouns|first_notempty:"she/her"))
        |set:"rawUserMessage":$input.onboarding_payload.raw_user_message
    }
  
    // --- Coordinates (KEEP AS NUMBERS — no to_text)
    var.update $external_api_payload {
      value = $external_api_payload
        |set:"p1Lat":($is_child ? $child_birth_place_coordinate.lat : $parent_birth_place_coordinate.lat)
        |set:"p1Lon":($is_child ? $child_birth_place_coordinate.lon : $parent_birth_place_coordinate.lon)
        |set:"p2Lat":($is_child ? $parent_birth_place_coordinate.lat : $child_birth_place_coordinate.lat)
        |set:"p2Lon":($is_child ? $parent_birth_place_coordinate.lon : $child_birth_place_coordinate.lon)
    }
  
    // --- Dates (formatted once, consistently)
    var.update $external_api_payload {
      value = $external_api_payload
        |set:"p1Birthday":(($is_child ? $input.onboarding_payload.child_dob : $input.onboarding_payload.user_dob) |format_timestamp:"Y-m-d\\TH:i")
        |set:"p2Birthday":(($is_child ? $input.onboarding_payload.user_dob :$input.onboarding_payload.child_dob) | format_timestamp:"Y-m-d\\TH:i")
    }
  
    // relationship_focus : Tells about the relationship with the person for whome user is generating the insight
    // reader_role : What is user to that person for whom we are generating the insight. User role can be "parent" or "adult_child" 
    // |set:"relationship_focus":($input.user_relation ? $input.user_relation : "parent")
    var.update $external_api_payload {
      value = $external_api_payload
        |set:"relationship_focus":($is_child ? "parent" : "child")
        |set:"reader_role":($is_child ? "adult_child" : "parent")
    }
  
    // --- Nested person objects
    var.update $external_api_payload {
      value = $external_api_payload
        |set:"person_1":```
          {
            birthday: (($is_child ? $input.onboarding_payload.child_dob : $input.onboarding_payload.user_dob) | format_timestamp:"Y-m-d\\TH:i"),
            lat: ($is_child ? $child_birth_place_coordinate.lat : $parent_birth_place_coordinate.lat),
            lon: ($is_child ? $child_birth_place_coordinate.lon : $parent_birth_place_coordinate.lon)
          }
          ```
        |set:"person_2":```
          {
            birthday: (($is_child ? $input.onboarding_payload.user_dob : $input.onboarding_payload.child_dob) | format_timestamp:"Y-m-d\\TH:i"),
            lat: ($is_child ? $parent_birth_place_coordinate.lat : $child_birth_place_coordinate.lat),
            lon: ($is_child ? $parent_birth_place_coordinate.lon : $child_birth_place_coordinate.lon)
          }
          ```
    }
  
    // --- Tone inputs
    var.update $external_api_payload {
      value = $external_api_payload
        |set:"tone_inputs":```
          {
            q1_climate: $input.onboarding_payload.climate,
            q2_activation: $input.onboarding_payload.activation,
            q3_closeness: $input.onboarding_payload.closeness,
            q4_posture: $input.onboarding_payload.posture
          }
          ```
    }
  
    // Update the User_01 table with the parent's birth coordinates
    // db.edit "User" {
    //   field_name = "id"
    //   field_value = $user_id
    //   data = {
    //     lat : $parent_birth_place_coordinate.lat
    //     lon : $parent_birth_place_coordinate.lon
    //     name: $input.onboarding_payload.username
    //   }
    // } as $updated_user_01
  
    // Generate a unique UUID for the request_id field
    security.create_uuid as $request_uuid
  
    // Create new insight record
    db.add Insights {
      enforce_hidden_fields = false
      data = {
        real_user_id        : $user_id
        child_id            : $input.child_id
        journey_id          : $input.journey_id
        status              : "processing"
        insights_api_payload: $external_api_payload
        request_id          : $request_uuid
      }
    } as $insight_record
  
    // Define max retries for the API call
    var $max_retries {
      value = 5
    }
  
    // Defining teaser variable that will get the teaser values once the external api gives the response
    var $_teaser {
      value = ""
    }
  
    // Loop to retry API call up to max_retries
    for ($max_retries) {
      each as $attempt {
        try_catch {
          try {
            // Trigger external API with extended timeout
            api.request {
              url = $env.EXTERNAL_INSIGHT_API_URL
              method = "POST"
              params = $external_api_payload
              headers = []
                |push:"Content-Type: application/json"
              timeout = 300
            } as $api_response
          
            // Check response status code
            conditional {
              if ($api_response.response.status == 200) {
                db.edit Insights {
                  field_name = "id"
                  field_value = $insight_record.id
                  enforce_hidden_fields = false
                  data = {
                    status      : "ready"
                    deep_text   : $api_response.response.result.deep
                    summary_text: $api_response.response.result.summary
                    teaser_text : $api_response.response.result.teaser
                  }
                } as $insight_record
              
                var.update $_teaser {
                  value = $api_response.response.result.teaser
                }
              
                // $_teaser = $api_response.response.result.teaser
              
                // Exit the loop on success
                break
              }
            
              else {
                throw {
                  name = "APIError"
                  value = "External API returned status " ~ $api_response.response.status
                }
              }
            }
          }
        
          catch {
            // Determine error message
            var $error_msg {
              value = $api_response.response.result.error
            }
          
            conditional {
              if ($error_msg == null) {
                var.update $error_msg {
                  value = $error.message
                }
              }
            }
          
            // Log the error for this attempt
            db.edit Insights {
              field_name = "id"
              field_value = $insight_record.id
              enforce_hidden_fields = false
              data = {
                last_error: "Attempt " ~ ($attempt + 1) ~ " failed: " ~ $error_msg
              }
            } as $insight_record
          
            // If this was the last attempt, mark as failed
            conditional {
              if ($attempt == ($max_retries - 1)) {
                db.edit Insights {
                  field_name = "id"
                  field_value = $insight_record.id
                  enforce_hidden_fields = false
                  data = {status: "failed"}
                } as $insight_record
              }
            }
          }
        }
      }
    }
  
    db.get Insights {
      field_name = "child_id"
      field_value = $input.child_id
    } as $Insights1
  
    conditional {
      if ($has_purchase) {
        api.request {
          url = "https://mamas-medicine-frontend-rosy.vercel.app/api/send-insight"
          method = "POST"
          params = {
            childName : $input.onboarding_payload.childname
            parentName: $input.onboarding_payload.username
            email     : $user.email
            insight   : $Insights1
          }
        
          headers = []
            |push:"Content-Type: application/json"
          timeout = 300
        } as $api_response
      }
    }
  }

  response = {
    message             : "Insight created successfully."
    insight_id          : $insight_record.id
    status              : $insight_record.status
    external_api_payload: $external_api_payload
    teaser              : $_teaser
  }
}