DEFINE TABLE feeddata SCHEMAFULL;

DEFINE FIELD state ON feedata TYPE number DEFAULT 0;

DEFINE FIELD url ON feeddata TYPE string;
DEFINE FIELD name ON feeddata TYPE string;
DEFINE FIELD description ON feeddata TYPE string;

DEFINE FIELD etag ON feedata TYPE string;
DEFINE FIELD last_updated ON feeddata TYPE datetime DEFAULT time::now();
DEFINE FIELD next_update ON feeddats TYPE datetime DEFAULT time::now();

DEFINE FIELD data ON feedata FLEXIBLE TYPE object;