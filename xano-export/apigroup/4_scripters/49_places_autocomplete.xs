// Autocomplete address search using Google Places API
query places_autocomplete verb=GET {
  api_group = "scripters"

  input {
    text q filters=trim|min:3
  }

  stack {
    // Set the limit of predictions to return (min 1, max 10)
    var $limit {
      value = 5
    }
  
    precondition (($input.q|strlen) >= 3) {
      error_type = "inputerror"
      error = "Search query must be at least 3 characters long."
    }
  
    var $base_url {
      value = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    }
  
    var $full_url {
      value = $base_url ~ "?input=" ~ ($input.q|url_encode) ~ "&key=" ~ $env.GOOGLE_GEOCODING_API_KEY
    }
  
    api.request {
      url = $full_url
      method = "GET"
    } as $google_response
  
    conditional {
      if ($google_response.response.result.status == "REQUEST_DENIED") {
        throw {
          name = "REQUEST_DENIED"
          value = $google_response.response.result.error_message
        }
      }
    }
  
    var $predictions {
      value = $google_response.response.result.predictions
    }
  
    array.map ($predictions) {
      by = {place_id: $this.place_id, description: $this.description}
    } as $formatted_predictions
  
    var $final_predictions {
      value = $formatted_predictions|slice:0:$limit
    }
  }

  response = {predictions: $final_predictions}
}