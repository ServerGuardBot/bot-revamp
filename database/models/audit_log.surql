DEFINE TABLE audit_log SCHEMALESS;

DEFINE FIELD guild_id ON audit_log TYPE string;

DEFINE FIELD originator_id ON audit_log TYPE string;
DEFINE FIELD event_name ON audit_log TYPE string;
DEFINE FIELD created_at ON audit_log TYPE datetime DEFAULT time::now();