query verify_otp verb=POST {
  api_group = "scripters"

  input {
    // The user's email address
    text email
  
    // The OTP code provided by the user
    text otp
  }

  stack {
    // Retrieve the user record by email
    db.get user {
      field_name = "email"
      field_value = $input.email
    } as $user
  
    // Ensure the user exists
    precondition ($user != null) {
      error_type = "inputerror"
      error = "User not found."
    }
  
    // Verify the OTP code matches
    precondition ($input.otp == $user.otp) {
      error_type = "inputerror"
      error = "Invalid OTP code. Please try again."
    }
  
    // Ensure the OTP has not expired
    precondition (now <= $user.otp_expiry) {
      error_type = "inputerror"
      error = "OTP has expired. Please request a new one."
    }
  
    // Clear the OTP fields after successful verification
    db.edit user {
      field_name = "id"
      field_value = $user.id
      enforce_hidden_fields = false
      data = {otp: null, otp_expiry: null}
    } as $updated_user
  }

  response = {message: "OTP verified successfully"}
}