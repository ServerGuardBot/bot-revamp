DEFINE TABLE user_identifier SCHEMALESS;

DEFINE FIELD connections ON user_identifier FLEXIBLE TYPE object;
DEFINE FIELD uses_vpn ON user_identifier TYPE bool DEFAULT false;
DEFINE FIELD hashed_ip ON user_identifier TYPE option<string>;
DEFINE FIELD browser_id ON user_identifier TYPE option<string>;