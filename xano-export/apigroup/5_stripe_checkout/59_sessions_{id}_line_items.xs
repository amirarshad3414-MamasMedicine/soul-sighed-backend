// When retrieving a Checkout Session, there is an includable line_items property containing the first handful of those items. There is also a URL where you can retrieve the full (paginated) list of line items.
query "sessions/{id}/line_items" verb=GET {
  api_group = "stripe_checkout"

  input {
    int limit?=10
    text starting_after? filters=trim
    text id? filters=trim
  }

  stack {
    var $params {
      value = {}|set:"limit":$input.limit
    }
  
    conditional {
      if ($input.starting_after != "") {
        var.update $params {
          value = $params
            |set:"starting_after":$input.starting_after
        }
      }
    }
  
    api.request {
      url = "https://api.stripe.com/v1/checkout/sessions/%s/line_items"|sprintf:$input.id
      method = "GET"
      params = $params
      headers = []
        |push:("Authorization: Basic %s"
          |sprintf:($env.stripe_api_secret|base64_encode)
        )
    } as $line_items
  
    precondition (($line_items.response.result|get:"error") == null) {
      error = $line_items.response.result.error.message
    }
  }

  response = $line_items.response.result
}