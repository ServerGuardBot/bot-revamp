DELETE user_token WHERE
    time::now() < created + type::duration("1d");
DELETE refresh_token_blacklist WHERE
    time::now() > expires;