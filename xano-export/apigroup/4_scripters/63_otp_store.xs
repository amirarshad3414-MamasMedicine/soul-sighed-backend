// Stores an externally generated OTP for password reset.
query "otp/store" verb=POST {
  api_group = "scripters"

  input {
    // The email address of the user.
    email email
  
    // The OTP generated externally to be stored.
    text otp
  
    // The expiry duration in seconds.
    int expiresIn
  }

  stack {
    // Retrieve the user record using the provided email.
    db.get user {
      field_name = "email"
      field_value = $input.email
    } as $user
  
    // Check if the user was found.
    precondition ($user != null) {
      error_type = "inputerror"
      error = "User not found"
    }
  
    // Get the current time in milliseconds.
    var $current_time {
      value = "now"|to_ms
    }
  
    // Calculate the expiry timestamp (now + expiresIn * 1000).
    var $expiry_timestamp {
      value = $current_time + ($input.expiresIn * 1000)
    }
  
    // Update the user record with the new OTP and expiry timestamp.
    db.edit user {
      field_name = "id"
      field_value = $user.id
      enforce_hidden_fields = false
      data = {otp: $input.otp, otp_expiry: $expiry_timestamp}
    } as $updated_user
  }

  response = {success: true, message: "OTP stored successfully"}
}