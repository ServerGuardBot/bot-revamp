SELECT user_id FROM guild_user WHERE
    guild_id = $guild AND
    $roles ANYINSIDE roles;