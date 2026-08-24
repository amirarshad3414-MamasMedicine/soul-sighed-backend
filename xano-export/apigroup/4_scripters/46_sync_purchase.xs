// Syncs a purchase record. Returns existing if found, creates new if not.
query sync_purchase verb=POST {
  api_group = "scripters"

  input {
    // The ID of the child associated with the purchase
    uuid child_id {
      table = "children"
    }
  
    // The ID of the journey associated with the purchase
    uuid journey_id {
      table = "Journey"
    }
  
    // The source or platform where the purchase was made
    text purchase_source? filters=trim
  
    // A unique reference identifier for the purchase
    text purchase_reference? filters=trim
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
  
    // Check if the user is authorized
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
  
    // Check if a purchase already exists for this user, child, and journey combination
    db.query Purchases {
      where = $db.Purchases.user_id == $user_id && $db.Purchases.child_id == $input.child_id && $db.Purchases.journey_id == $input.journey_id
      return = {type: "single"}
    } as $existing_purchase
  
    conditional {
      if ($existing_purchase != null) {
        var $purchase_record {
          value = $existing_purchase
        }
      
        var $message {
          value = "Purchase already exists"
        }
      }
    
      else {
        // Create a new purchase record if one does not exist
        db.add Purchases {
          enforce_hidden_fields = false
          data = {
            user_id           : $user_id
            child_id          : $input.child_id
            journey_id        : $input.journey_id
            purchase_source   : $input.purchase_source
            purchase_reference: $input.purchase_reference
          }
        } as $purchase_record
      
        var $message {
          value = "Purchase created successfully"
        }
      }
    }
  }

  response = {
    purchase_id: $purchase_record.id
    child_id   : $purchase_record.child_id
    journey_id : $purchase_record.journey_id
    message    : $message
  }
}