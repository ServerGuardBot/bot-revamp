DEFINE TABLE role_config SCHEMALESS;

DEFINE FIELD guild_id ON role_config TYPE string;
DEFINE FIELD role_id ON role_config TYPE string;

DEFINE FIELD type ON role_config TYPE string;

DEFINE FIELD created ON role_config TYPE datetime DEFAULT time::now() READONLY;