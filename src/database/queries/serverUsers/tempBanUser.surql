CREATE user_status SET
    type = "tempban",
    guild_id = $guild_id,
    user_id = $user_id,
    reason = $reason,
    ends = time::now() + type::duration($ends);