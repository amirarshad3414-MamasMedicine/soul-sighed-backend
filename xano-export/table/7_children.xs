// The table of children
table children {
  auth = false

  schema {
    uuid id
    timestamp created_at?=now {
      visibility = "private"
    }
  
    // Storing the id of parent of children to relate child to the Parents
    uuid? user_01_id?
  
    int user_id? {
      table = "user"
    }
  
    // The Name of  the Child
    text name? filters=trim
  
    // Date of Birth of Child
    date? date_of_birth?
  
    // Time of Birth of Children
    timestamp? time_of_birth?
  
    // Represent the lattitude of birth place of child
    decimal lat?
  
    // Represents the longitude of birth palce of child
    decimal lon?
  
    text? pronoun? filters=trim
    bool default_child?
  
    // This indicates the relationship type of the person with the user. If the relationship type is parent, the user is generating insights for the parent. If it is child, the user is generating insights for the child
    enum relationship_focus?=child {
      values = ["child", "parent"]
    }
  }

  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "created_at", op: "desc"}]}
    {
      type : "btree|unique"
      field: [
        {name: "user_01_id", op: "asc"}
        {name: "name", op: "asc"}
        {name: "date_of_birth", op: "asc"}
      ]
    }
  ]
}