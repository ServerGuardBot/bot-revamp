SELECT * FROM user_status WHERE
    type = "reminder" AND
    guild_id = $guild AND
    user_id = $user;