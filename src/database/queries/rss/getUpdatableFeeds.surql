SELECT * FROM channel_config WHERE
    type == "RSS" && $guilds CONTAINS guild_id;