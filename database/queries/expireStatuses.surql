DELETE user_status WHERE
    $ids CONTAINS meta::id(id);