// Fetches address details, coordinates, and country code from Google Places API based on a place_id.
query places_details verb=GET {
  api_group = "scripters"

  input {
    // The unique Google Place ID.
    text place_id
  }

  stack {
    // Call the Google Places Details API
    api.request {
      url = "https://maps.googleapis.com/maps/api/place/details/json"
      method = "GET"
      params = {}
        |set:"place_id":$input.place_id
        |set:"key":$env.GOOGLE_PLACES_AUTOCOMPLETE_API_KEY
        |set:"fields":"formatted_address,geometry,address_components"
    } as $api_response
  
    // Extract the body of the response
    var $response_body {
      value = $api_response.response.result
    }
  
    // Check if the API call was successful (status "OK")
    conditional {
      if ($response_body.status != "OK") {
        throw {
          name = "GooglePlacesError"
          value = "Failed to fetch place details: " ~ $response_body.status ~ " - " ~ $response_body.error_message
        }
      }
    }
  
    // Extract the result object
    var $place_details {
      value = $response_body.result
    }
  
    // Extract and convert coordinates
    var $lat {
      value = $place_details.geometry.location.lat|to_decimal
    }
  
    var $lon {
      value = $place_details.geometry.location.lng|to_decimal
    }
  
    // Validate coordinate ranges
    precondition ($lat >= -90 && $lat <= 90) {
      error_type = "inputerror"
      error = "Latitude must be between -90 and 90."
    }
  
    precondition ($lon >= -180 && $lon <= 180) {
      error_type = "inputerror"
      error = "Longitude must be between -180 and 180."
    }
  
    // Extract country code from address components using array.find to correctly handle iteration context
    array.find ($place_details.address_components) if (`$this.types|in:"country"`) as $country_component
  
    var $country_code {
      value = $country_component.short_name
    }
  
    // Assemble the final response object including place_id
    var $output_req {
      value = {
        place_id         : $input.place_id
        formatted_address: $place_details.formatted_address
        lat              : $lat
        lon              : $lon
        country_code     : $country_code
      }
    }
  }

  response = $output_req
}