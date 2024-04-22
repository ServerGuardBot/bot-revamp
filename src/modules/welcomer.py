from core.checks import is_module_enabled
from libs.formatter import SGFormatter
from guilded.ext import commands
from modules.image import Image
from datetime import datetime

import database as db
import guilded
import random

class Welcomer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def pick_image(self, images, image_cycle, member):
        image: Image = self.bot.get_cog("Image")
        if image_cycle == "Random":
            image_url = random.choice(images)
        elif image_cycle == "Daily":
            current_day = datetime.now().day
            image_url = images[current_day % len(images)]
        elif image_cycle == "Weekly":
            current_week = datetime.now().isocalendar()[1]
            image_url = images[current_week % len(images)]
        elif image_cycle == "Monthly":
            current_month = datetime.now().month
            image_url = images[current_month % len(images)]
        elif image_cycle == "PerUser":
            member_count = len(member.server.members)
            image_url = images[member_count % len(images)]
        else:
            image_url = images[0]
        
        # Have to proxy these because sometimes Guilded's image proxy
        # gets rejected by some websites.
        proxied = image.proxy_url(image_url)
        return proxied if proxied else image_url
    
    async def welcome_member(self, member: guilded.Member):
        if not is_module_enabled("welcomer"): return
        try:
            guild = await db.servers.fetch_or_create_server(member.server)
        except Exception as e:
            print("Failed to get guild: {} - {}".format(type(e).__name__, e))
        else:
            if guild.settings.get("send_welcome", False):
                try:
                    channel = await member.server.getch_channel(guild.settings.get("welcome_channel"))
                except:
                    pass
                else:
                    template = guild.settings.get("welcome_message", "Welcome, {mention} to {server_name}!")
                    images = guild.settings.get("welcome_image", [])
                    image_cycle = guild.settings.get("welcome_image_cycle", "Random")
                    
                    sgf = SGFormatter(member.server)
                    message = sgf.format(template, mention=member.mention, server_name=member.server.name)

                    image = self.pick_image(images, image_cycle, member)

                    em = guilded.Embed(
                        title="Welcome!",
                        description=message,
                    )
                    if image:
                        em.set_image(url=image)
                    try:
                        await channel.send(embed=em)
                    except Exception as e:
                        print("Failed to send welcome message: {} - {}".format(type(e).__name__, e))
    
    async def farewell_member(self, member: guilded.Member):
        if not is_module_enabled("welcomer"): return
        try:
            guild = await db.servers.fetch_or_create_server(member.server)
        except Exception as e:
            print("Failed to get guild: {} - {}".format(type(e).__name__, e))
        else:
            if is_module_enabled("verification", member):
                unverified_role = guild.settings.get("unverified_role")
                verified_role = guild.settings.get("verified_role")
                is_verified = False
                roles = await member.fetch_role_ids()
                if verified_role and verified_role in roles:
                    is_verified = True
                if unverified_role and unverified_role in roles:
                    is_verified = False
                if not is_verified:
                    return

            if guild.settings.get("send_goodbye", False):
                try:
                    channel = await member.server.getch_channel(guild.settings.get("goodbye_channel"))
                except:
                    pass
                else:
                    template = guild.settings.get("goodbye_message", "Goodbye, {mention}!")
                    images = guild.settings.get("goodbye_image", [])
                    image_cycle = guild.settings.get("goodbye_image_cycle", "Random")

                    sgf = SGFormatter(member.server)
                    message = sgf.format(template, mention=member.mention)

                    image = self.pick_image(images, image_cycle, member)

                    em = guilded.Embed(
                        title="Goodbye!",
                        description=message
                    )
                    if image:
                        em.set_image(url=image)
                    try:
                        await channel.send(embed=em)
                    except Exception as e:
                            print("Failed to send goodbye message: {} - {}".format(type(e).__name__, e))

    @commands.Cog.listener()
    async def on_member_join(self, event: guilded.MemberJoinEvent):
        if is_module_enabled("verification", event): return
        await self.welcome_member(event.member)
    
    @commands.Cog.listener()
    async def on_member_remove(self, event: guilded.MemberRemoveEvent):
        await self.farewell_member(event.member)

def setup(bot: commands.Bot):
    bot.add_cog(Welcomer(bot))