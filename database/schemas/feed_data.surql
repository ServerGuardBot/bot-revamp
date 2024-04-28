DEFINE TABLE feeddata SCHEMAFULL;

DEFINE FIELD state ON feeddata TYPE string DEFAULT "ALIVE" ASSERT $value IN ["ALIVE", "DEAD"];

DEFINE FIELD url ON feeddata TYPE string;
DEFINE FIELD name ON feeddata TYPE string;
DEFINE FIELD description ON feeddata TYPE string DEFAULT "";

DEFINE FIELD etag ON feeddata TYPE option<string>;
DEFINE FIELD last_updated ON feeddata TYPE datetime DEFAULT time::now();
DEFINE FIELD next_update ON feeddata TYPE datetime DEFAULT time::now();

DEFINE FIELD data ON feeddata FLEXIBLE TYPE object;