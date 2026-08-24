// Sync user from Memberstack or return existing user
query sync_user verb=POST {
  api_group = "scripters"

  input {
  }

  stack {
    // Grab the Authorization header from the request
    var $auth_header {
      value = $env.$http_headers|get:"Authorization"
    }
  
    // Ensure the header is present, otherwise return 401 Unauthorized
    precondition ($auth_header != null && $auth_header != "") {
      error_type = "unauthorized"
      error = "Missing Authorization token in header of Request"
    }
  
    // Ensure the header is formatted as a Bearer token
    precondition ($auth_header|starts_with:"Bearer ") {
      error_type = "unauthorized"
      error = "Invalid Authorization header format. Expected Bearer token."
    }
  
    // Extract the actual token by removing the Bearer prefix
    var $memberstack_token {
      value = $auth_header|replace:"Bearer ":""|trim
    }
  
    // Decode and verify the token, catching any errors (invalid/expired) to return 401
    try_catch {
      try {
        security.jws_decode {
          token = $memberstack_token
          key = $env.MEMBERSTACK_JWK
          check_claims = {}
          signature_algorithm = "RS256"
          timeDrift = 0
        } as $crypto_1
      
        // Ensure the decoded token contains an ID
        precondition ($crypto_1.id != null) {
          error_type = "unauthorized"
          error = "Invalid token payload: missing user ID"
        }
      }
    
      catch {
        // Throwing an error with the name 'unauthorized' guarantees a 401 status code in Xano
        util.set_header {
          value = "Status: 401 Unauthorized"
          duplicates = "replace"
        }
      
        var $res_invalid_token {
          value = {access: false, message: "Invalid or expired token"}
        }
      
        return {
          value = {payload: $res_invalid_token}
        }
      }
    }
  
    // Retrieve the user from the database
    db.get User_01 {
      field_name = "memberstack_id"
      field_value = $crypto_1.id
    } as $user_01
  
    conditional {
      if ($user_01 != null) {
        // User exists, prepare the response
        var $response_data {
          value = {message: "User already exists", user: $user_01}
        }
      }
    
      else {
        // Fetch user details from Memberstack 
        api.request {
          url = "https://admin.memberstack.com/members/" ~ $crypto_1.id
          method = "GET"
          headers = []
            |push:"X-API-KEY: " ~ $env.memberstack_v2_api_key
        } as $memberstack_response
      
        // Create the new user in the database
        db.add User_01 {
          enforce_hidden_fields = false
          data = {
            email         : $memberstack_response.response.result.data.auth.email
            memberstack_id: $memberstack_response.response.result.data.id
            name          : ($memberstack_response.response.result.data.customFields["last-name"]|is_empty) ? $memberstack_response.response.result.data.customFields["first-name"] : ($memberstack_response.response.result.data.customFields["first-name"] ~ " " ~ $memberstack_response.response.result.data.customFields["last-name"])
          }
        } as $new_user
      
        // Prepare the response for the newly created user
        var $response_data {
          value = {message: "User created successfully", user: $new_user}
        }
      }
    }
  }

  response = $response_data
}