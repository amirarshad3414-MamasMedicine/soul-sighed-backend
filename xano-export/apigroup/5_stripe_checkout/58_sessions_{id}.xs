// Retrieves a Session object.
query "sessions/{id}" verb=GET {
  api_group = "stripe_checkout"

  input {
    text id? filters=trim
  }

  stack {
    api.request {
      url = "https://api.stripe.com/v1/checkout/sessions/%s"|sprintf:$input.id
      method = "GET"
      headers = []
        |push:("Authorization: Basic %s"
          |sprintf:($env.stripe_api_secret|base64_encode)
        )
    } as $stripe_session
  
    precondition (($stripe_session.response.result|get:"error") == null) {
      error = $stripe_session.response.result.error.message
    }
  }

  response = $stripe_session.response.result
}