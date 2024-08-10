from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder, UserPermissions
from database.exceptions import DatabaseError
from surrealdb.ws import SurrealException
from database.types import to_datetime

from ..servers import ChannelConfig

class RSSFeed(ChannelConfig):
    def __init__(self, data: dict):
        super().__init__(data)

        self.preset = data['preset']
        self.webhook = data.get('webhook')
        self.ping_role = data.get('ping_role')
        self.last_update = to_datetime(data.get('last_update'))
        self.known = data.get('known', [])
        self.extra_fields = data.get('extra_fields', {})
        self.filters = data.get('filters', [])
        
        self.extra_data: dict = {}
        for key, value in data.items():
            if key not in ['preset', 'webhook', 'ping_role', 'last_update', 'guild_id', 'channel_id', 'type', 'created', 'known', 'id', 'extra_fields']:
                self.extra_data[key] = value
    
    async def update(self, **kwargs):
        await super().update(**kwargs)
        valkey.set(f"db:rss_feeds:{self.id}", encoder.encode(self.raw), 700)