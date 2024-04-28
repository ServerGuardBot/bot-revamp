DEFINE TABLE user_token SCHEMALESS;

DEFINE FIELD type ON user_token TYPE string;
DEFINE FIELD created ON user_token TYPE datetime DEFAULT time::now() READONLY;