DEFINE TABLE feed_preset SCHEMAFULL;

DEFINE FIELD url ON feed_preset TYPE string DEFAULT "";
DEFINE FIELD name ON feed_preset TYPE string;
DEFINE FIELD description ON feed_preset TYPE string DEFAULT "";

DEFINE FIELD extra_fields ON feed_preset FLEXIBLE TYPE object DEFAULT {};