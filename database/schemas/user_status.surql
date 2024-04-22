DEFINE TABLE user_status SCHEMALESS;

DEFINE FIELD guild_id ON user_status TYPE string;
DEFINE FIELD user_id ON user_status TYPE string;
DEFINE FIELD type ON user_status TYPE string;

DEFINE FIELD created ON user_status TYPE datetime DEFAULT time::now();
DEFINE FIELD ends ON user_status TYPE option<datetime>;