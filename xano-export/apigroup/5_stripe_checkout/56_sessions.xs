// Creates a Session object.
query sessions verb=POST {
  api_group = "stripe_checkout"

  input {
    // User redirect url upon successful payment
    text success_url? filters=trim
  
    // User redirect url on cancel of stripe checkout process
    text cancel_url? filters=trim
  
    json[] line_items?
  }

  stack {
    api.request {
      url = "https://api.stripe.com/v1/checkout/sessions"
      method = "POST"
      params = {}
        |set:"success_url":$input.success_url
        |set:"cancel_url":$input.cancel_url
        |set:"payment_method_types[0]":"card"
        |set:"consent_collection[promotions]":"auto"
        |set:"line_items":$input.line_items
        |set:"mode":"payment"
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