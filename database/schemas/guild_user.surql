DEFINE TABLE guild_user SCHEMALESS;

DEFINE FIELD guild_id ON guild_user TYPE string;
DEFINE FIELD user_id ON guild_user TYPE string;
DEFINE FIELD perms ON guild_user TYPE string DEFAULT "";
DEFINE FIELD xp ON guild_user TYPE number DEFAULT 0;
DEFINE FIELD can_access_dash ON guild_user TYPE bool DEFAULT false;
DEFINE FIELD is_banned ON guild_user TYPE bool DEFAULT false;
DEFINE FIELD bypass_verification ON guild_user TYPE bool DEFAULT false;
DEFINE FIELD roles ON guild_user TYPE array<number> DEFAULT [];

DEFINE FIELD join_date ON guild_user TYPE datetime DEFAULT time::now();

DEFINE INDEX guildUserIndex ON guild_user COLUMNS guild_id, id UNIQUE;