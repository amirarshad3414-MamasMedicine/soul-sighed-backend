// Returns a list of Checkout Sessions.
query sessions verb=GET {
  api_group = "stripe_checkout"

  input {
    // Only return the Checkout Session for the PaymentIntent specified
    bool? payment_intent?
  
    // A cursor for use in pagination. starting_after is an object ID that defines your place in the list. For instance, if you make a list request and receive 100 objects, ending with obj_foo, your subsequent call can include starting_after=obj_foo in order to fetch the next page of the list.
    text? starting_after? filters=trim
  
    // A limit on the number of objects to be returned, between 1 and 100.
    int limit?=10
  
    // A cursor for use in pagination. ending_before is an object ID that defines your place in the list. For instance, if you make a list request and receive 100 objects, starting with obj_bar, your subsequent call can include ending_before=obj_bar in order to fetch the previous page of the list.
    text? ending_before? filters=trim
  
    // Only return the Checkout Session for the subscription specified.
    bool? subscription?
  }

  stack {
    var $params {
      value = {}
        |set:"payment_intent":$input.payment_intent
        |set:"limit":$input.limit
        |set:"ending_before":$input.ending_before
        |set:"starting_after":$input.starting_after
        |set:"subscription":$input.subscription
    }
  
    api.request {
      url = "https://api.stripe.com/v1/checkout/sessions"
      method = "GET"
      params = $params
      headers = []
        |push:("Authorization: Basic %s"
          |sprintf:($env.stripe_api_secret|base64_encode)
        )
    } as $stripe_sessions
  
    precondition (($stripe_sessions.response.result|get:"error") == null) {
      error = $stripe_sessions.response.result.error.message
    }
  }

  response = $stripe_sessions.response.result
}