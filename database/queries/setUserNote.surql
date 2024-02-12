UPDATE guild_user SET
    note = $note
WHERE guild_id = $guild_id AND user_id = $user_id