DEFINE TABLE channel_config SCHEMALESS;

DEFINE FIELD guild_id ON channel_config TYPE string;
DEFINE FIELD channel_id ON channel_config TYPE string;

DEFINE FIELD type ON channel_config TYPE string;

DEFINE FIELD created ON channel_config TYPE datetime DEFAULT time::now();