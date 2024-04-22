SELECT meta::id(id) AS id, source_url, data FROM image WHERE
    meta::id(id) == $id OR source_url == $source_url;