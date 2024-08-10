CREATE giveaway SET
    guild_id = $guild,
    channel_id = $channel,
    message_id = $message,
    ends_at = time::from::secs($duration),
    ended = time::now() > time::from::secs($duration),
    prize = $prize,
    hosted_by = $host,
    winner_amount = $winners,
    winners = $winner_list OR [],
    entries = $entries OR [];