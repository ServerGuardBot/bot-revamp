UPDATE guild_user SET
    roles = $roles
WHERE guild_id = $guild AND user_id = $id;