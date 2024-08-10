CREATE feeddata SET
    url = $url,
    name = $name,
    description = $description,
    etag = $etag,
    last_updated = time::from::unix($last_updated),
    next_update = time::from::unix($next_update),
    data = $data;