// Process purchase webhook and handle email or child reference
query checkout verb=POST {
  api_group = "scripters"

  input {
    json __self?
  }

  stack {
    var $event {
      value = $input.__self
    }
  
    var $obj {
      value = $event.data.object
    }
  
    var $send_email {
      value = $obj.metadata.send_email|to_bool
    }
  
    debug.log {
      value = "Webhook received"
    }
  
    conditional {
      if ($obj.client_reference_id) {
        var $child_id {
          value = $obj.client_reference_id
        }
      
        db.get children {
          field_name = "id"
          field_value = $child_id
        } as $child
      
        db.get user {
          field_name = "id"
          field_value = $child.user_id
        } as $user
      
        db.get Purchases {
          field_name = "child_id"
          field_value = $child_id
        } as $model
      
        conditional {
          if ($model == null) {
            db.add Purchases {
              enforce_hidden_fields = false
              data = {
                created_at        : "now"
                user_id           : $user.id
                child_id          : $child.id
                journey_id        : "fff90478-924f-4ec7-95a1-68b5549a0ec9"
                purchase_source   : "stripe"
                purchase_reference: $obj.id
              }
            } as $model
          }
        }
      
        var $email {
          value = $user.email
        }
      }
    
      else {
        db.add Purchases {
          enforce_hidden_fields = false
          data = {
            created_at        : "now"
            email             : $obj.customer_details.email
            purchase_reference: $obj.id
            purchase_source   : "stripe"
            journey_id        : "fff90478-924f-4ec7-95a1-68b5549a0ec9"
            user_id           : null
            child_id          : null
          }
        } as $new_purchase
      
        var $email {
          value = $obj.customer_details.email
        }
      }
    }
  
    api.request {
      url = "https://a.klaviyo.com/api/profile-subscription-bulk-create-jobs/"
      method = "POST"
      params = {
        data: {
          type: "profile-subscription-bulk-create-job"
          attributes: {
            profiles: {
              data: [
                {
                  type: "profile"
                  attributes: {
                    email: $email
                  }
                }
              ]
            }
          }
          relationships: {
            list: {
              data: {
                type: "list"
                id  : "XPSdCW"
              }
            }
          }
        }
      }
    
      headers = []
        |push:"Authorization: Klaviyo-API-Key pk_ab8d15bcfa308fb2790a4ea13c34b277e2"
        |push:"Content-Type: application/json"
        |push:"revision: 2024-02-15"
    } as $klaviyo_response
  
    debug.log {
      value = $klaviyo_response
    }
  
    api.request {
      url = "https://parenting-insights.soul-sighted.com/api/send-purchase-email"
      method = "POST"
      params = {
        data: {
          customer: $obj.customer_details,
          product_purchase: "Your Parenting Dynamic",
          purchase_id: $obj.id,
          child_name: $child.name
        }
      }
    } as $api1
  
    debug.log {
      value = $api1
    }
  
    conditional {
      if ($send_email) {
        db.get Insights {
          field_name = "child_id"
          field_value = $child_id
        } as $insight_record
      
        api.request {
          url = "https://mamas-medicine-frontend-rosy.vercel.app/api/send-insight"
          method = "POST"
          params = {
            childName : $child.name
            parentName: $user.name
            email     : $email
            insight   : $insight_record
          }
        
          headers = []
            |push:"Content-Type: application/json"
          timeout = 300
        } as $send_insight_response
      }
    }
  }

  response = {success: true}
}