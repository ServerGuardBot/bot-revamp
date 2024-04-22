CREATE user_token SET
    type = "login",
    location = $location,
    browser = $browser,
    platform = $platform,
    lock = $lock;