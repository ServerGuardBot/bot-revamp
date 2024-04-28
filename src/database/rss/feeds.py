from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder, UserPermissions
from database.exceptions import DatabaseError
from surrealdb.ws import SurrealException

from ..servers import ChannelConfig

class RSSFeed(ChannelConfig):
    def __init__(self, data: dict):
        super().__init__(data)

        self.preset = data['preset']
        self.webhook = data.get('webhook')
        self.ping_role = data.get('ping_role')
        self.last_update = data['last_update']
        self.known = data['known']
        
        self.extra_data: dict = {}
        for key, value in data.items():
            if key not in ['preset', 'webhook', 'ping_role', 'last_update', 'guild_id', 'channel_id', 'type', 'created', 'known']:
                self.extra_data[key] = value