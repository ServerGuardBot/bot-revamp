SELECT * FROM user_identifier
    WHERE connections CONTAINSANY $connections
    AND $ids CONTAINS meta::id(id);