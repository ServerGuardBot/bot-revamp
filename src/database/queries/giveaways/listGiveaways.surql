SELECT * FROM giveaway WHERE guild_id = $guild
    LIMIT BY 10 START AT $page;
SELECT count() FROM giveaway WHERE guild_id = $guild GROUP BY count;