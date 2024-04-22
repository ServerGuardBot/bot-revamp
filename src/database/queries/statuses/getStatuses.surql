SELECT * FROM user_status WHERE
    $types CONTAINS type AND
    guild_id = $guild_id AND
    user_id = $user_id;