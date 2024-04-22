from core.checks_api import authenticated, dashboard_access, has_permissions
from core.embeds import EMBED_STANDARD, EMBED_DENIED, EMBED_SUCCESS
from quart import Quart, jsonify, request
from quart_cors import route_cors
from guilded.ext import commands
from guilded.http import Route
from core import checks

import guilded
import config

class Developer(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command()
    @checks.developer_only()
    async def load(self, ctx: commands.Context, module: str):
        """Loads a module."""
        module = f"modules.{module}"
        try:
            self.bot.load_extension(module)
        except Exception as e:
            em = EMBED_DENIED(title="Module Load Error", description=f"Error loading `{module}`\n```{e}```")
            await ctx.reply(embed=em)
            print('{}: {}'.format(type(e), e))
        else:
            em = EMBED_SUCCESS(title="Module Loaded", description=f"Loaded `{module}`")
            await ctx.reply(embed=em)

    @commands.command()
    @checks.developer_only()
    async def unload(self, ctx: commands.Context, module: str):
        module = f"modules.{module}"
        if module in bot.extensions:
            self.bot.unload_extension(module)
            em = EMBED_SUCCESS(title="Module Unloaded", description=f"Unloaded `{module}`")
            await ctx.reply(embed=em)
        else:
            em = EMBED_DENIED(title="Module Not Loaded", description=f"Module `{module}` is not loaded")
            await ctx.reply(embed=em)

    @commands.command()
    @checks.developer_only()
    async def reload(self, ctx: commands.Context, module: str=None):
        if module == None:
            em = EMBED_STANDARD(title="Bot Reload", description="Reloading bot")
            await ctx.reply(embed=em)
            os.execv(sys.executable, ['python'] + sys.argv)
        else:
            module = f"modules.{module}"
            try:
                self.bot.unload_extension(module)
                self.bot.load_extension(module)
            except Exception as e:
                em = EMBED_DENIED(title="Module Reload Error", description=f"Error reloading `{module}`\n```{e}```")
                await ctx.reply(embed=em)
                print('{}: {}'.format(type(e), e))
            else:
                em = EMBED_SUCCESS(title="Module Reloaded", description=f"Reloaded `{module}`")
                await ctx.reply(embed=em)

def setup(bot: commands.Bot):
    bot.add_cog(Developer(bot))