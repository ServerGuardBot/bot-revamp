import os

TOKEN: str = os.getenv('TOKEN')
SUPPORT_SERVER_ID: str = os.getenv('SUPPORT_SERVER_ID')
DEVELOPER_ROLE_ID: str = os.getenv('DEVELOPER_ROLE_ID')
PREMIUM_ROLE_ID: str = os.getenv('PREMIUM_ROLE_ID')
DEFAULT_PREFIX: str = os.getenv('DEFAULT_PREFIX', "/")
LOGIN_CHANNEL_ID: str = os.getenv('LOGIN_CHANNEL_ID')

INVITE_LINK: str = os.getenv('INVITE_LINK')
SUPPORT_SERVER_LINK: str = os.getenv('SUPPORT_SERVER_LINK')

SSL_CERTIFICATE: str = os.getenv('SSL_CERTIFICATE', './certs/cert.pem')
SSL_KEY: str = os.getenv('SSL_KEY', './certs/key.pem')

DATABASE_IP: str = os.getenv('DATABASE_IP', 'localhost')
DATABASE_PORT: str = os.getenv('DATABASE_PORT', '8000')
DATABASE_USER: str = os.getenv('DATABASE_USER', 'surrealdb')
DATABASE_PASSWORD: str = os.getenv('DATABASE_PASSWORD', 'Password123')

DATABASE_NAMESPACE: str = os.getenv('DATABASE_NAMESPACE', 'server_guard')
DATABASE_DB: str = os.getenv('DATABASE_DB', 'prod')

SESSION_SECRET: str = os.getenv('SESSION_SECRET')
ORIGIN_SITE: str = os.getenv('ORIGIN_SITE', "https://serverguard.xyz")
API_SITE: str = os.getenv('API_SITE', "https://api.serverguard.xyz")