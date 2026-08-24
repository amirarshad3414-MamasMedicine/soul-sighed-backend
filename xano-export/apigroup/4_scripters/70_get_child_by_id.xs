// auth = "user" 
// Return the record found in the database
query get_child_by_id verb=GET {
  api_group = "scripters"
  auth = "user"

  input {
    // The ID of the child passed via query parameters (?child_id=value)
    text child_id
  }

  stack {
    // Fetches a single record from the children table by its ID
    db.query children {
      where = $db.children.id == $input.child_id
      return = {type: "single"}
    } as $child_record
  
    // // Optional Security Check: Ensure the logged-in user actually owns this child record
    precondition ($child_record.user_id == $auth.id) {
      error_type = "unauthorized"
      error = "You do not have permission to view this record."
    }
  }

  response = $child_record
}