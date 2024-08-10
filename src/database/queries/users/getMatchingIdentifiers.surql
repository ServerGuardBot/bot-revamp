SELECT * FROM user_identifier
    WHERE $ids CONTAINS meta::id(id)
    AND (
        object::entries(connections) CONTAINSANY object::entries($connections) OR
        hashed_ip == $hashed_ip OR
        browser_id == $browser_id
    );