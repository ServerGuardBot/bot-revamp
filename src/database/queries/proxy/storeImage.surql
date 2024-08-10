CREATE image SET
    source_url = $source_url,
    data = $data,
    expires = time::now() + type::duration($expires);