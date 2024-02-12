CREATE refresh_token_blacklist SET
    id = $id,
    expires = time::from::unix($expires);