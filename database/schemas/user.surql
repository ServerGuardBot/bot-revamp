DEFINE TABLE user SCHEMALESS;

DEFINE FIELD avatar ON user TYPE string;
DEFINE FIELD name ON user TYPE string;
DEFINE FIELD language ON user TYPE string DEFAULT "en";

DEFINE FIELD created ON user TYPE datetime DEFAULT time::now() READONLY;
DEFINE FIELD updated ON user TYPE datetime VALUE time::now() DEFAULT time::now();

DEFINE INDEX userNameIndex ON TABLE user COLUMNS name SEARCH ANALYZER ascii BM25 HIGHLIGHTS;