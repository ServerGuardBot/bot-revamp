BEGIN TRANSACTION;
UPDATE type::thing("feeddata", $id) MERGE $payload;
IF $last_updated != NONE && $last_updated != NULL THEN
    ( UPDATE type::thing("feeddata", $id) SET last_updated = time::from::unix($last_updated) )
END;
IF $next_update != NONE && $next_update != NULL THEN
    ( UPDATE type::thing("feeddata", $id) SET next_update = time::from::unix($next_update) )
END;
COMMIT TRANSACTION;