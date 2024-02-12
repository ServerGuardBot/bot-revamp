from database import DBConnection, loadQuery, resultExists
from core.embeds import EMBED_STANDARD
from guilded.utils import hyperlink
from guilded.ext import commands

import itertools
import config
import guilded

class HelpCommand(commands.DefaultHelpCommand):
    def __init__(self, **options):
        super().__init__(**options)
        
        self.verify_checks = True
        self.paginator = commands.Paginator(prefix=None, suffix=None)
        self.aliases_heading = "Aliases:"
    
    async def send_pages(self):
        """A helper utility to send the page output from :attr:`paginator` to the destination."""
        destination = self.get_destination()
        for page in self.paginator.pages:
            await destination.send(embed=EMBED_STANDARD(
                title="Help", # TODO: i18n support
                description=page,
            ).add_field(
                name="Links",
                value=f"{hyperlink(title='Support', link=config.SUPPORT_SERVER_LINK)} • {hyperlink(title='Website', link='https://serverguard.xyz')} • {hyperlink(title='Invite', link=config.INVITE_LINK)}",
                inline=False
            )
            )
        return destination
    
    async def get_ending_note(self):
        return (
            f"Use {self.context.clean_prefix}help `command` for more info on a command."
        )
    
    async def add_bot_commands_formatting(self, commands, heading):
        """Adds the minified bot heading with commands to the output.
        The formatting should be added to the :attr:`paginator`.
        The default implementation is a bold underline heading followed
        by commands separated by an EN SPACE (U+2002) in the next line.
        Parameters
        -----------
        commands: Sequence[:class:`Command`]
            A list of commands that belong to the heading.
        heading: :class:`str`
            The heading to add to the line.
        """
        if commands:
            joined = ', '.join([f"`{c.name}`" for c in commands])
            self.paginator.add_line(f'__**{heading}**__')
            self.paginator.add_line(joined)
    
    async def add_subcommand_formatting(self, command):
        """Adds formatting information on a subcommand.
        The formatting should be added to the :attr:`paginator`.
        The default implementation is the prefix and the :attr:`Command.qualified_name`
        optionally followed by an En dash and the command's :attr:`Command.short_doc`.
        Parameters
        -----------
        command: :class:`Command`
            The command to show information of.
        """
        fmt = '`{0}` \N{EN DASH} {1}' if command.short_doc else '`{0}`'
        self.paginator.add_line(fmt.format(command.qualified_name, command.short_doc))
    
    def add_aliases_formatting(self, aliases):
        """Adds the formatting information on a command's aliases.
        The formatting should be added to the :attr:`paginator`.
        The default implementation is the :attr:`aliases_heading` bolded
        followed by a comma separated list of aliases.
        This is not called if there are no aliases to format.
        Parameters
        -----------
        aliases: Sequence[:class:`str`]
            A list of aliases to format.
        """
        self.paginator.add_line(f'**{self.aliases_heading}** {", ".join([f"`{c}`" for c in aliases])}', empty=True)
    
    async def add_command_formatting(self, command):
        """A utility function to format commands and groups.
        Parameters
        ------------
        command: :class:`Command`
            The command to format.
        """

        if command.description:
            self.paginator.add_line(command.description, empty=True)

        signature = self.get_command_signature(command)
        if command.aliases:
            self.paginator.add_line(signature)
            self.add_aliases_formatting(command.aliases)
        else:
            self.paginator.add_line(signature, empty=True)

        if command.help:
            try:
                self.paginator.add_line(command.help, empty=True)
            except RuntimeError:
                for line in command.help.splitlines(): 
                    self.paginator.add_line(line)
                self.paginator.add_line()
    
    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        # TODO: Apply i18n to aliases_heading

        if bot.description:
            self.paginator.add_line(bot.description, empty=True)
        
        no_category = f'\u200b{self.no_category}'

        def get_category(command, *, no_category=no_category):
            cog = command.cog
            return cog.qualified_name if cog is not None else no_category

        filtered = await self.filter_commands(bot.commands, sort=True, key=get_category)
        to_iterate = itertools.groupby(filtered, key=get_category)

        for category, commands in to_iterate:
            commands = sorted(commands, key=lambda c: c.name) if self.sort_commands else list(commands)
            await self.add_bot_commands_formatting(commands, category)

        note = await self.get_ending_note()
        if note:
            self.paginator.add_line()
            self.paginator.add_line(note)

        await self.send_pages()
    
    async def send_cog_help(self, cog):
        bot = self.context.bot
        if bot.description:
            self.paginator.add_line(bot.description, empty=True)

        if cog.description:
            self.paginator.add_line(cog.description, empty=True)

        filtered = await self.filter_commands(cog.get_commands(), sort=self.sort_commands)
        if filtered:
            self.paginator.add_line(f'**{cog.qualified_name} {self.commands_heading}**')
            for command in filtered:
                await self.add_subcommand_formatting(command)

            note = await self.get_ending_note()
            if note:
                self.paginator.add_line()
                self.paginator.add_line(note)

        await self.send_pages()

    async def send_group_help(self, group):
        await self.add_command_formatting(group)

        filtered = await self.filter_commands(group.commands, sort=self.sort_commands)
        if filtered:

            self.paginator.add_line(f'**{self.commands_heading}**')
            for command in filtered:
                await self.add_subcommand_formatting(command)

            note = await self.get_ending_note()
            if note:
                self.paginator.add_line()
                self.paginator.add_line(note)

        await self.send_pages()

    async def send_command_help(self, command):
        await self.add_command_formatting(command)
        self.paginator.close_page()
        await self.send_pages()

class Bot(commands.Bot):
    async def process_message(self, message: guilded.Message):
        # A hacky method to parse the message's mentions and then replace them
        # in the message with their appropriate formats for easier command parsing
        for user in message.mentions:
            found_mention = message.content.find(f'@{user.display_name}') != -1
            if not found_mention:
                try:
                    user = message.server.get_member(user.id)
                    if not user.nick:
                        user = await message.server.fetch_member(user.id)
                        self.http.add_to_member_cache(user)
                except:
                    pass
            name = user.nick or user.name
            message.content = message.content.replace(f'@{name}', f'<@{user.id}>')
        for channel in message.channel_mentions:
            message.content = message.content.replace(f'#{channel.name}', f'<#{channel.id}>')
        for role in message.role_mentions:
            message.content = message.content.replace(f'@{role.name}', f'<@{role.id}>')

    async def on_message(self, event: guilded.MessageEvent):
        message = event.message
        await self.process_message(message)
        await self.process_commands(message)
    
    async def on_message_edit(self, event: guilded.MessageUpdateEvent):
        await self.process_message(event.after)
    
    async def on_message_delete(self, event: guilded.MessageDeleteEvent):
        await self.process_message(event.message)

async def prefix(bot: Bot, message: guilded.ChatMessage):
    async with DBConnection() as db:
        guildData = await db.query(loadQuery('guildData'), {
            'guild': message.server_id,
        })
        if resultExists(guildData):
            return commands.when_mentioned_or(guildData[0]["result"][0].get("prefix", config.DEFAULT_PREFIX))(bot, message)
    return commands.when_mentioned_or(config.DEFAULT_PREFIX)(bot, message)
