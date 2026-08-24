query add_children verb=POST {
  api_group = "scripters"
  auth = "user"

  input {
    // Name of the child
    text name filters=trim
  
    // Relationship_focus 
    text relationship_focus filters=trim
  
    // Date of birth of the child
    date? dob?
  
    // Place of birth
    text? place_of_birth? filters=trim
  
    // Google Place ID for the place of birth
    text? place_of_birth_id? filters=trim
  
    // Pronoun of the child
    text? pronoun? filters=trim
  }

  stack {
    var $latitude {
      value = null
    }
  
    var $longitude {
      value = null
    }
  
    conditional {
      if ($input.place_of_birth_id != null) {
        api.request {
          url = "https://maps.googleapis.com/maps/api/place/details/json"
          method = "GET"
          params = {}
            |set:"place_id":$input.place_of_birth_id
            |set:"key":$env.GOOGLE_GEOCODING_API_KEY
        } as $google_response
      
        var.update $latitude {
          value = $google_response.response.result.result.geometry.location.lat
        }
      
        var.update $longitude {
          value = $google_response.response.result.result.geometry.location.lng
        }
      }
    }
  
    db.query children {
      where = $db.children.user_id == $auth.id && $db.children.name == $input.name && $db.children.date_of_birth ==? $input.dob
      return = {type: "exists"}
    } as $child_exists
  
    precondition ($child_exists == false) {
      error_type = "inputerror"
      error = "Record already exists"
    }
  
    db.add children {
      enforce_hidden_fields = false
      data = {
        user_id           : $auth.id
        name              : $input.name
        date_of_birth     : $input.dob
        lat               : $latitude
        lon               : $longitude
        pronoun           : $input.pronoun
        relationship_focus: $input.relationship_focus
      }
    } as $new_child
  
    var $response_data {
      value = $new_child
    }
  
    conditional {
      if ($input.place_of_birth_id != null) {
        var.update $response_data {
          value = $response_data
            |set:"place_id":$input.place_of_birth_id
        }
      }
    }
  }

  response = $response_data
}