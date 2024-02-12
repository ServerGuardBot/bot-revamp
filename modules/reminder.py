from core.embeds import EMBED_DENIED, EMBED_STANDARD, EMBED_SUCCESS
from database import DBConnection, loadQuery, resultExists
from humanfriendly import parse_timespan, InvalidTimespan
from guilded.ext import commands, tasks

import guilded

class Reminder(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.reminder.add_command(self.remindme)
        self.reminder.add_command(self.list_reminders)
        self.reminder.add_command(self.remove_reminder)
        self.check_reminders.start()
    
    @commands.group(name="reminder", invoke_without_command=True)
    async def reminder(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.reply(embed=EMBED_DENIED(
                title="Invalid Command",
                description="Please use a valid subcommand."
            ))
    
    @commands.command(name="add")
    async def remindme(self, ctx: commands.Context, duration: str, *message: str):
        try:
            parse_timespan(duration)
        except InvalidTimespan:
            raise commands.CommandError("Invalid duration.")

        async with DBConnection() as db:
            result = await db.query(loadQuery("addReminder"), {
                "user_id": ctx.author.id,
                "guild_id": ctx.server.id,
                "channel_id": ctx.channel.id,
                "message_id": ctx.message.id,
                "message": " ".join(message),
                "ends": duration
            })
            if result[0]["status"] == "OK":
                await ctx.reply(embed=EMBED_SUCCESS(
                    title="Reminder Added",
                    description=f'Created reminder with id **{result[0]["result"][0]["id"].split(":")[1]}.**'
                ))
            else:
                raise commands.CommandError("Failed to add reminder.")
    
    @commands.command(name="list")
    async def list_reminders(self, ctx: commands.Context):
        async with DBConnection() as db:
            request = await db.query(loadQuery("getUserReminders"), {
                "user": ctx.author.id,
                "guild": ctx.server.id,
            })
            if request[0]["status"] == "OK" and resultExists(request):
                await ctx.reply(embed=EMBED_STANDARD(
                    title="Reminders",
                    description="\n".join([f'**{reminder["id"].split(":")[1]}:** {reminder["message"]}' for reminder in request[0]["result"]])
                ))
            else:
                await ctx.reply(embed=EMBED_STANDARD(
                    title="Reminders",
                    description="You have no reminders."
                ))
    
    @commands.command(name="remove")
    async def remove_reminder(self, ctx: commands.Context, id: str):
        async with DBConnection() as db:
            result = await db.query(loadQuery("removeStatus"), {
                "id": id,
            })
            if result[0]["status"] == "OK":
                await ctx.reply(embed=EMBED_SUCCESS(
                    title="Reminder Removed",
                    description=f'Removed reminder with id **{id}.**'
                ))
            else:
                raise commands.CommandError("Failed to remove reminder.")
    
    @tasks.loop(seconds=5)
    async def check_reminders(self):
        async with DBConnection() as db:
            # TODO: Maybe limit this query in scope to only
            # TODO: users the bot is aware of?
            request = await db.query(loadQuery("getExpiredStatuses"), {
                "types": ["reminder"]
            })
            if request[0]["status"] == "OK" and resultExists(request):
                reminder_ids = []
                for reminder in request[0]["result"]:
                    try:
                        server = await self.bot.getch_server(reminder["guild_id"])
                        channel: guilded.ChatChannel = await server.getch_channel(reminder["channel_id"])
                        message = self.bot.get_message(reminder["message_id"]) or await channel.fetch_message(reminder["message_id"])

                        await message.reply(embed=EMBED_STANDARD(
                            title="Reminder Expired",
                            description=reminder["message"]
                        ), private=True)
                        reminder_ids.append(reminder["id"].split(":")[1])
                    except Exception as e:
                        print(e)
                        continue
                result = await db.query(loadQuery("expireStatuses"), {
                    "ids": reminder_ids,
                })
                print(result)

def setup(bot: commands.Bot):
    bot.add_cog(Reminder(bot))