from database import DBConnection, loadQuery, resultExists, valkey, encoder, decoder, DatabaseModel
from database.exceptions import DatabaseError, NotFound
from database.types import to_datetime, to_string
from surrealdb.ws import SurrealException
from core.embeds import EMBED_STANDARD
from guilded.ext import commands
from enum import Enum

import database as db
import guilded
import random

class GiveawayState(Enum):
    ACTIVE = 'active'
    ENDED = 'ended'
    CANCELLED = 'cancelled'

class Giveaway(DatabaseModel):
    def __init__(self, data: dict):
        super().__init__(data)
        
        self.guild_id = data['guild_id']
        self.channel_id = data['channel_id']
        self.message_id = data['message_id']
        
        self.ends_at = to_datetime(data['ends_at'])
        self.ended = data['ended']
        self.ended_by = to_string(data['ended_by'])
        
        self.prize = data['prize']
        self.host = data['hosted_by']
        
        self.winner_amount = data['winner_amount']
        self.winners = data.get('winners', [])
        
        self.entries = data.get('entries', [])
    
    @property
    def total_entries(self) -> int:
        return len(self.entries)
    
    @property
    def state(self) -> GiveawayState:
        if self.ended:
            if len(self.winners) == 0:
                return GiveawayState.CANCELLED
            else:
                return GiveawayState.ENDED
        if datetime.now() > self.ends_at:
            return GiveawayState.ENDED
        return GiveawayState.ACTIVE
    
    def _roll_winners(self):
        if len(self.entries) == 0:
            return []
        elif len(self.entries) <= self.winner_amount:
            return [entry for entry in self.entries]
        else:
            winners = []
            for i in range(self.winner_amount):
                winner = None
                while winner is None or winner in winners:
                    winner = random.choice(self.entries)
                winners.append(winner)
            return winners
    
    async def update(self, **kwargs):
        for key in kwargs:
            if key in ['created_at', 'guild_id', 'channel_id', 'message_id'] or kwargs[key] is None:
                kwargs.pop(key)
        async with DBConnection() as db:
            try:
                result = await db.query(loadQuery('updateGiveaway'), {
                    "id": self.id,
                    "payload": kwargs
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(result):
                    for key, value in kwargs.items():
                        setattr(self, key, value)
                        self.raw[key] = result[0]['result'][0].get(key, self.raw.get(key))
                    valkey.set(f"giveaway:{self.id}", encoder.encode(self.raw), 86400)
                else:
                    raise DatabaseError(f"Failed to update giveaway: {str(result[0]['result'][0])}")
    
    async def end(self, bot: commands.Bot, guild: db.servers.Server, ended_by: str = None):
        await self.update(
            ended=True,
            ended_by=ended_by,
            winners=self._roll_winners()
        )
        channel: guilded.ChatChannel = await bot.getch_channel(self.channel_id)
        message = await channel.fetch_message(self.message_id)
        await message.edit(
            embed=EMBED_STANDARD(
                title=f"Giveaway hosted by <@{self.host}>"
            ).add_field(
                name="Prize",
                value=self.prize,
                inline=False
            ).add_field(
                name="Winners",
                value=self.winner_amount,
                inline=True
            ).add_field(
                name="Ends In",
                value="OVER",
                inline=True
            ).add_field(
                name="Who Won",
                value=", ".join(self.winners),
                inline=False
            )
        )
        await message.reply(embed=EMBED_STANDARD(
            title="Giveaway Ended",
            description=f"The giveaway has ended! The winner(s) are {', '.join(self.winners)}."
        ))
    
    async def cancel(self, bot: commands.Bot, guild: db.servers.Server, cancelled_by: str = None):
        await self.update(
            ended=True,
            ended_by=cancelled_by,
            winners=[]
        )
        channel: guilded.ChatChannel = await bot.getch_channel(self.channel_id)
        message = await channel.fetch_message(self.message_id)
        await message.edit(
            embed=EMBED_STANDARD(
                title=f"Giveaway hosted by <@{self.host}>"
            ).add_field(
                name="Prize",
                value=self.prize,
                inline=False
            ).add_field(
                name="Winners",
                value=self.winner_amount,
                inline=True
            ).add_field(
                name="Ends In",
                value="CANCELLED",
                inline=True
            ).add_field(
                name="Who Won",
                value="Nobody",
                inline=False
            )
        )
        await message.reply(embed=EMBED_STANDARD(
            title="Giveaway Cancelled",
            description=f"The giveaway has been cancelled."
        ))
    
    async def reroll(self, bot: commands.Bot, guild: db.servers.Server, rerolled_by: str = None):
        await self.update(
            ended=True,
            ended_by=rerolled_by,
            winners=self._roll_winners()
        )
        channel: guilded.ChatChannel = await bot.getch_channel(self.channel_id)
        message = await channel.fetch_message(self.message_id)
        await message.edit(
            embed=EMBED_STANDARD(
                title=f"Giveaway hosted by <@{self.host}>"
            ).add_field(
                name="Prize",
                value=self.prize,
                inline=False
            ).add_field(
                name="Winners",
                value=self.winner_amount,
                inline=True
            ).add_field(
                name="Ends In",
                value="OVER",
                inline=True
            ).add_field(
                name="Who Won",
                value=", ".join(self.winners),
                inline=False
            )
        )
        await message.reply(embed=EMBED_STANDARD(
            title="Giveaway Rerolled",
            description=f"The giveaway has been rerolled! The winner(s) are {', '.join(self.winners)}."
        ))
    
    async def delete(self, bot: commands.Bot, guild: db.servers.Server, deleted_by: str):
        async with DBConnection() as db:
            try:
                result = await db.query(loadQuery('deleteGiveaway'), {
                    "id": self.id
                })
            except SurrealException as e:
                raise DatabaseError(str(e))
            else:
                if resultExists(result):
                    valkey.delete(f"giveaway:{self.id}")

                    try:
                        channel: guilded.ChatChannel = await bot.getch_channel(self.channel_id)
                        message = await channel.fetch_message(self.message_id)
                        await message.delete()
                    except:
                        pass
                else:
                    raise DatabaseError(f"Failed to delete giveaway: {str(result[0]['result'][0])}")
    
    async def add_entry(self, user_id: str):
        if user_id not in self.entries:
            self.entries.append(user_id)
            await self.update(entries=self.entries)
    
    async def remove_entry(self, user_id: str):
        if user_id in self.entries:
            self.entries.remove(user_id)
            await self.update(entries=self.entries)