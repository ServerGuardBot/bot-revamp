SELECT * FROM user_status WHERE
    $types CONTAINS type AND
    ends < time::now();