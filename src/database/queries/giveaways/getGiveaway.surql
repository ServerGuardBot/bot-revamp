SELECT * FROM giveaway WHERE
    guild_id == $guild AND
    meta::id(id) == $id OR message_id == $message;