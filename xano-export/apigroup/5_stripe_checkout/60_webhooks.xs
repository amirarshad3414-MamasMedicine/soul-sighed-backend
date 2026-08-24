// Webhook endpoint for checkout session 
query webhooks verb=POST {
  api_group = "stripe_checkout"

  input {
    json __self?
  }

  stack {
    var $webhook_data {
      value = $input.__self.data.object
    }
  
    db.add session {
      enforce_hidden_fields = false
      data = {
        created_at       : "now"
        session_id       : $webhook_data.id
        customer_id      : $webhook_data.customer
        amount_subtotal  : $webhook_data.amount_subtotal
        amount_total     : $webhook_data.amount_total
        payment_intent_id: $webhook_data.payment_intent
        payment_status   : $webhook_data.payment_status
      }
    } as $session_1
  
    conditional {
      if ($webhook_data.consent.promotions == "opt_in") {
        api.request {
          url = "https://mamas-medicine-frontend-rosy.vercel.app/subscribe-marketing"
          method = "POST"
          params = {email: $webhook_data.customer_details.email}
          headers = []
            |push:"Content-Type: application/json"
        } as $marketing_res
      }
    }
  }

  response = $session_1
}