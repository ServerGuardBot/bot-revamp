CREATE image SET
    source_url = $source_url,
    data = $data,
    expires = time::now() + type::duration($expires)
RETURN meta::id(id) AS id, source_url, data;