SELECT * FROM image WHERE
    meta::id(id) == $id OR source_url == $source_url;