CREATE user_status SET
    type = "warn",
    guild_id = $guild_id,
    user_id = $user_id,
    reason = $reason,
    issuer = $issuer.
    ends = time::now() + type::duration($ends);