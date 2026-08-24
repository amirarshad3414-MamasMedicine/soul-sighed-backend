// Creates a Session object.
query create_checkout_session verb=POST {
  api_group = "scripters"

  input {
    // User redirect url upon successful payment
    text success_url? filters=trim
  
    // User redirect url on cancel of stripe checkout process
    text cancel_url? filters=trim
  
    json[] line_items?
    text? client_reference_id? filters=trim
    text? customer_email? filters=trim
    bool send_email?
  }

  stack {
    api.request {
      url = "https://api.stripe.com/v1/checkout/sessions"
      method = "POST"
      params = {}
        |set:"success_url":$input.success_url
        |set:"cancel_url":$input.cancel_url
        |set:"payment_method_types[0]":"card"
        |set:"client_reference_id":$input.client_reference_id
        |set:"line_items":$input.line_items
        |set_ifnotempty:"customer_email":$input.customer_email
        |set:"mode":"payment"
        |set:"allow_promotion_codes":"true"
        |set:"metadata":{send_email: ($input.send_email | first_notempty: false)}
      headers = []
        |push:("Authorization: Basic %s"
          |sprintf:($env.stripe_key|base64_encode)
        )
    } as $stripe_session
  
    precondition (($stripe_session.response.result|get:"error") == null) {
      error = $stripe_session.response.result.error.message
    }
  }

  response = $stripe_session.response.result
}