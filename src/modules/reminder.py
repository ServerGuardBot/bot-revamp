from core.embeds import EMBED_DENIED, EMBED_STANDARD, EMBED_SUCCESS
from humanfriendly import parse_timespan, InvalidTimespan
from guilded.ext import commands, tasks

import database as db
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

        try:
            guild = await db.servers.fetch_or_create_server(ctx.server)
            user = await guild.fetch_or_create_member(ctx.author)
            status = await user.create_reminder(
                message=" ".join(message),
                message_id=ctx.message.id,
                channel_id=ctx.channel.id,
                ends=duration
            )
        except:
            raise commands.CommandError("Failed to add reminder.")
        else:
            await ctx.reply(embed=EMBED_SUCCESS(
                title="Reminder Added",
                description=f'Created reminder with id **{status.id}.**'
            ))
    
    @commands.command(name="list")
    async def list_reminders(self, ctx: commands.Context):
        try:
            reminders = await db.statuses.get_statuses(["reminder"], ctx.server.id, ctx.author.id)
        except:
            raise commands.CommandError("Failed to get reminders.")
        else:
            await ctx.reply(embed=EMBED_STANDARD(
                title="Reminders",
                description="\n".join([f'**{reminder.id}:** {reminder.message}' for reminder in reminders])
            ))
    
    @commands.command(name="remove")
    async def remove_reminder(self, ctx: commands.Context, id: str):
        try:
            status = await db.statuses.get_status(id)
            if status.type != "reminder" or status.user_id != ctx.author.id or status.guild_id != ctx.server.id:
                raise commands.CommandError("Invalid reminder id.")
            await status.delete()
        except:
            raise commands.CommandError("Failed to remove reminder.")
        else:
            await ctx.reply(embed=EMBED_SUCCESS(
                title="Reminder Removed",
                description=f'Removed reminder with id **{id}.**'
            ))
    
    @tasks.loop(seconds=5)
    async def check_reminders(self):
        # TODO: Maybe limit this query in scope to only
        # TODO: users the bot is aware of?
        try:
            reminders = await db.statuses.get_expired_statuses(["reminder"])
        except:
            pass
        else:
            reminder_ids = []
            for reminder in reminders:
                try:
                    server = await self.bot.getch_server(reminder.guild_id)
                    channel: guilded.ChatChannel = await server.getch_channel(reminder.channel_id)
                    message = self.bot.get_message(reminder.message_id) or await channel.fetch_message(reminder.message_id)

                    await message.reply(embed=EMBED_STANDARD(
                        title="Reminder Expired",
                        description=reminder.message
                    ), private=True)
                    reminder_ids.append(reminder.id)
                except guilded.errors.NotFound:
                    reminder_ids.append(reminder.id)
                except guilded.errors.Forbidden:
                    reminder_ids.append(reminder.id)
                except Exception as e:
                    # Only keep the reminder in the database if
                    # the issue was caused by our bot, not by Guilded
                    print(e)
                    continue
            try:
                await db.statuses.expire_statuses(reminder_ids)
            except:
                pass

def setup(bot: commands.Bot):
    bot.add_cog(Reminder(bot))