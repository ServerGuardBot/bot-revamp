DEFINE TABLE analytics_item SCHEMAFULL;

DEFINE FIELD key ON analytics_item TYPE string;
DEFINE FIELD date ON analytics_item TYPE datetime DEFAULT time::now();
DEFINE FIELD score ON analytics_item TYPE number DEFAULT 0;

DEFINE INDEX analyticsKeyIndex ON analytics_item COLUMNS key, date UNIQUE;