CREATE user_status SET
    type = "reminder",
    guild_id = $guild_id,
    user_id = $user_id,
    message_id = $message_id,
    channel_id = $channel_id,
    message = $message,
    ends = time::now() + type::duration($ends);