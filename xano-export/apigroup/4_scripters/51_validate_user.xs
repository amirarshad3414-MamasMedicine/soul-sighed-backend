// Extracts JWT from headers, calls Memberstack API to decode/verify, and retrieves the corresponding User_01 record.
query validate_user verb=GET {
  api_group = "scripters"

  input {
  }

  stack {
    // Grab the Authorization header from the request
    var $auth_header {
      value = $env.$http_headers|get:"Authorization"
    }
  
    // 401 : Ensure the Authorization in header is present, otherwise return 401 Unauthorized
    var $res_missing {
      value = {
        access : false
        message: "Missing Authorization token in header of Request"
      }
    }
  
    precondition ($auth_header != null && $auth_header != "") {
      error_type = "unauthorized"
      payload = $res_missing
    }
  
    // 401 : Case when Bearer word is not defined just before the token. Ensure the header is formatted as a Bearer token  
    var $res_format {
      value = {
        access : false
        message: "Invalid Authorization header format. Expected Bearer token."
      }
    }
  
    precondition ($auth_header|starts_with:"Bearer ") {
      error_type = "unauthorized"
      payload = $res_format
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
      
        // 401 : Ensure the decoded token contains an ID
        var $res_missing_id {
          value = {
            access : false
            message: "Invalid token payload: missing user ID"
          }
        }
      
        precondition ($crypto_1.id != null) {
          error_type = "unauthorized"
          payload = $res_missing_id
        }
      }
    
      catch {
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
  
    // Return 404 not found if user does not exist 
    var $res_no_user {
      value = {
        access : false
        message: "No user found against this token"
      }
    }
  
    precondition ($user_01 != null) {
      error_type = "notfound"
      payload = $res_no_user
    }
  
    var $res_user {
      value = {
        access : true
        message: "User authenticated successfully"
        data   : $user_01
      }
    }
  
    var $formatted_response {
      value = {payload: $res_user}
    }
  }

  response = $formatted_response
}