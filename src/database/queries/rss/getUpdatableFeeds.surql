SELECT * FROM channel_config WHERE
    type == "RSS" &&
    last_updated < $updated &&
    ($urls CONTAINS url OR $presets CONTAINS preset);