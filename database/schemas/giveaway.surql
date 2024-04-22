DEFINE TABLE giveaway SCHEMAFULL;

DEFINE FIELD guild_id ON giveaway TYPE string;
DEFINE FIELD channel_id ON giveaway TYPE string;
DEFINE FIELD message_id ON giveaway TYPE string;

DEFINE FIELD ended ON giveaway TYPE bool DEFAULT false;
DEFINE FIELD ends_at ON giveaway TYPE datetime;

DEFINE FIELD prize ON giveaway TYPE string;
DEFINE FIELD hosted_by ON giveaway TYPE string;

DEFINE FIELD winner_amount ON giveaway TYPE number;
DEFINE FIELD winners ON giveaway TYPE array<string>;
DEFINE FIELD winners.* ON giveaway TYPE string;

DEFINE FIELD entries ON giveaway TYPE array<string>;
DEFINE FIELD entries.* ON giveaway TYPE string;