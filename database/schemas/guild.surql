DEFINE TABLE guild SCHEMALESS;

DEFINE FIELD premium ON guild TYPE string DEFAULT '0';
DEFINE FIELD subscription_id ON guild TYPE option<string>;

DEFINE FIELD active ON guild TYPE bool DEFAULT true;
DEFINE FIELD last_active ON guild TYPE datetime VALUE time::now() DEFAULT time::now();

DEFINE FIELD name ON guild TYPE string;
DEFINE FIELD bio ON guild TYPE option<string>;
DEFINE FIELD avatar ON guild TYPE option<string>;
DEFINE FIELD members ON guild TYPE number DEFAULT 1;

DEFINE FIELD first_seen ON guild TYPE datetime DEFAULT time::now();

DEFINE INDEX guildNameIndex ON TABLE guild COLUMNS name SEARCH ANALYZER ascii BM25 HIGHLIGHTS;
DEFINE INDEX guildBioIndex ON TABLE guild COLUMNS bio SEARCH ANALYZER ascii BM25 HIGHLIGHTS;