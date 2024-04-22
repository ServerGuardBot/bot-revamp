SELECT id as meta::id(id), * FROM user_identifier
    WHERE $ids CONTAINS meta::id(id)
    AND (
        connections CONTAINSANY $connections OR
        hashed_ip == $hashed_ip OR
        browser_id == $browser_id
    );