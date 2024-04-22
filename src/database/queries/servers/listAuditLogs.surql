SELECT *, meta::id(id) AS id FROM audit_log WHERE
    guild_id = $guild AND
    ($authors IS NULL || $authors CONTAINS originator_id) AND
    ($event_names IS NULL || $event_names CONTAINS event_name) AND
    ($range_start IS NULL || created_at >= time::from::secs($range_start)) AND
    ($range_end IS NULL || created_at <= time::from::secs($range_end))
ORDER BY created_at DESC
LIMIT $limit
START $page * $limit;
SELECT count() FROM (SELECT * FROM audit_log WHERE
    guild_id = $guild AND
    ($authors IS NULL || $authors CONTAINS originator_id) AND
    ($event_names IS NULL || $event_names CONTAINS event_name) AND
    ($range_start IS NULL || created_at >= time::from::secs($range_start)) AND
    ($range_end IS NULL || created_at <= time::from::secs($range_end))
) GROUP BY count;