from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from core.converters import MemberConverter
from datetime import timedelta, datetime
from guilded.ext import commands, tasks
from humanfriendly import format_number
from core.checks import listener
from modules.image import Image
from guilded.http import Route
from guilded import Object
from libs.canvas import *

import database as db
import requests
import guilded
import config
import math
import io

DEFAULT_BANNER_URL = "https://images.unsplash.com/photo-1519638399535-1b036603ac77"

def get_cooldown_key(message: guilded.ChatMessage):
    return (message.author.id, message.server.id)

class XP(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.level_role_cache = {}
        
        self.xp_cooldowns = {}

        self.purge_cache.start()
    
    @tasks.loop(seconds=1)
    async def purge_cache(self):
        for key in list(self.level_role_cache.keys()):
            item = self.level_role_cache[key]
            if item[0] - datetime.now() < timedelta(seconds=0):
                del self.level_role_cache[key]
    
    @commands.command()
    async def rank(self, ctx: commands.Context, member: MemberConverter=None):
        image: Image = self.bot.get_cog("Image")
        if member is None:
            member = ctx.author
        xp = await member.award_xp(0)
        user = await self.bot.fetch_user(member.id)
        
        card = generate_rank_card(
            xp=xp,
            name=member.display_name,
            level=get_level(xp),
            avatar=member.display_avatar.url,
            banner=user.banner and user.banner.url or DEFAULT_BANNER_URL,
            total_xp=get_xp(get_level(xp) + 1),
            leveled_up=False,
            rank=1,
        )
        
        image_id = await image.store_bytes(card)

        em = guilded.Embed().set_image(
            url=f"{config.API_SITE}/resource/ext/{image_id}"
        )
        await ctx.reply(embed=em)
    
    async def xp_updated(self, member: guilded.Member, prev_xp: int, xp: int):
        try:
            guild = await db.servers.fetch_or_create_server(member.server)
        except Exception as e:
            return
        else:
            if guild.settings.get("announce_level_up", False):
                prev_level = get_level(prev_xp)
                level = get_level(xp)
                if level > prev_level:
                    user = await self.bot.getch_user(member.id)
                    
                    card = generate_rank_card(
                        xp=xp,
                        name=member.display_name,
                        level=get_level(xp),
                        avatar=member.display_avatar.url,
                        banner=user.banner and user.banner.url or DEFAULT_BANNER_URL,
                        total_xp=get_xp(get_level(xp) + 1),
                        leveled_up=True,
                        rank=1,
                    )
                    
                    image_id = await image.store_bytes(card)
                    
                    em = guilded.Embed().set_image(
                        url=f"{config.API_SITE}/resource/ext/{image_id}"
                    )
                    
                    if getattr(member, "last_message"):
                        await member.last_message.reply(embed=em)
    
    @commands.Cog.listener()
    async def on_bot_remove(self, event: guilded.BotRemoveEvent):
        if self.xp_cooldowns.get(event.server.id):
            del self.xp_cooldowns[event.server.id]
            self.xp_cooldowns[event.server.id] = None
    
    @listener("xp")
    @commands.Cog.listener()
    async def on_bulk_member_xp_add(self, event: guilded.BulkMemberXpAddEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except Exception as e:
            return
        else:
            if guild.settings.get("remove_old_level_roles", False):
                cached = self.level_role_cache.get(event.server.id)
                if cached:
                    cached = cached[1]
                else:
                    level_roles_req = (
                        await self.bot.http.request(
                            Route('GET', f'/teams/{event.server_id}/level_rewards', override_base=Route.USER_BASE)
                        )
                    ) or []
                    cached = [{
                        "level": r["level"],
                        "id": r["teamRoleId"],
                    } for r in level_roles_req]
                    self.level_role_cache[message.server.id] = [datetime.now() + timedelta(minutes=10), cached]
                for member in event.members:
                    lower_roles, highest_role = [], {'level': 0, 'id': -3429785678456}
                    for role in level_roles:
                        role: dict
                        if role['id'] in member._role_ids:
                            if role['level'] >= highest_role['level']:
                                if role['level'] != highest_role['level'] and highest_role['level'] > 0:
                                    # Only add the highest role to lower_roles if the level is actually lower than this role
                                    lower_roles.append(highest_role['id'])
                                highest_role = role
                    if len(lower_roles) > 0:
                        for role in lower_roles:
                            await member.remove_role(Object(role))
    
    @listener("xp")
    @commands.Cog.listener()
    async def on_message(self, event: guilded.MessageEvent):
        message = event.message
        if message.author.bot:
            return
        try:
            guild = await db.servers.fetch_or_create_server(message.server)
        except Exception as e:
            return
        else:
            xp_roles = guild.settings.get("xp_roles")
            if xp_roles:
                member_role_ids = message.author._role_ids
                if any(int(role_id) in member_role_ids for role_id in xp_roles):
                    guild_xp_cooldown = self.xp_cooldowns.get(message.server.id)
                    if not guild_xp_cooldown:
                        self.xp_cooldowns[message.server.id] = commands.CooldownMapping.from_cooldown(1, 60, get_cooldown_key)
                        guild_xp_cooldown = self.xp_cooldowns[message.server.id]
                    if not guild_xp_cooldown.update_rate_limit(message):
                        amt = 0
                        for role_id in xp_roles:
                            if int(role_id) in member_role_ids:
                                amt += xp_roles[role_id]
                        await message.author.award_xp(amt)
                        
def setup(bot: commands.Bot):
    bot.add_cog(XP(bot))

def generate_rank_card(
    name: str,
    level: str,
    xp: str,
    total_xp: str,
    rank: str,
    leveled_up: bool,
    avatar: str,
    banner: str
):
    if len(name) > 17:
        # Truncate the name so nothing weird happens
        name = name[:17] + "..."

    prev_total = get_xp(int(level) - 1)
    xp_amount = xp - prev_total

    avatar_size = (150, 150)
    avatar_offset = (10, 10)
    
    text_padding = 5

    canvas = Canvas(900, 290, background=(0, 0, 0, 0))
    dominant_color = canvas.get_dominant_color(banner)
    panel_alpha = int(255 * .5)
    
    rl_bounds = canvas.text_bounds(
        (0, 0),
        "Rank",
        26
    )
    rl_bounds = (rl_bounds[0], rl_bounds[1], rl_bounds[2] + 3, rl_bounds[3])
    rank_bounds = canvas.text_bounds(
        (0, 0),
        f"#{format_number(rank)}",
        32,
        bold=True
    )
    rank_bounds = (rank_bounds[0], rank_bounds[1], rank_bounds[2] + 3, rank_bounds[3])
    ll_bounds = canvas.text_bounds(
        (0, 0),
        "Level",
        26
    )
    ll_bounds = (ll_bounds[0], ll_bounds[1], ll_bounds[2] + 3, ll_bounds[3])
    level_bounds = canvas.text_bounds(
        (0, 0),
        format_number(level),
        32,
        bold=True
    )
    level_bounds = (level_bounds[0], level_bounds[1], level_bounds[2] + 3, level_bounds[3])
    bound_size = (
        canvas.bound_width(rl_bounds) +
        canvas.bound_width(rank_bounds) +
        canvas.bound_width(ll_bounds) +
        canvas.bound_width(level_bounds),
        max(
            canvas.bound_height(rl_bounds),
            canvas.bound_height(rank_bounds),
            canvas.bound_height(ll_bounds),
            canvas.bound_height(level_bounds)
        )
    )
    bound_size = (
        bound_size[0] + text_padding * 2,
        bound_size[1] + text_padding * 2
    )
    bound_offset = (
        canvas.width - 10,
        10
    )
    bound_start = (
        (bound_offset[0] - bound_size[0]) + text_padding,
        bound_offset[1] + text_padding
    )
    bound_bottom = bound_start[1] + bound_size[1] - text_padding * 2
    
    name_bounds = canvas.text_bounds(
        (0, 0),
        name,
        32,
        bold=True
    )
    name_bounds = (
        name_bounds[0] - text_padding,
        name_bounds[1] - text_padding,
        name_bounds[2] + text_padding,
        name_bounds[3] + text_padding
    )
    name_offset = (
        canvas.width - 10 - canvas.bound_width(name_bounds),
        10 + 10 + bound_size[1]
    )
    name_center = (
        name_offset[0] + (name_bounds[2] - name_bounds[0]) // 2,
        name_offset[1] + (name_bounds[3] - name_bounds[1]) // 2
    )
    
    xp_offset = (
        canvas.width - 10,
        canvas.height - 10
    )
    xp_size = (470, 85)
    
    xp_bounds = canvas.text_bounds(
        (0, 0),
        format_number(int(xp)),
        24,
        bold=True
    )
    xp_total_bounds = canvas.text_bounds(
        (0, 0),
        f"/{int(total_xp)}",
        18,
        anchor="lb",
        bold=True
    )
    
    canvas.rounded_rectangle(
        (0, 0),
        (900, 290),
        (0, 0),
        6,
        image=banner
    )
    
    canvas.ellipse(
        (avatar_offset[0], avatar_offset[1]),
        (avatar_offset[0] + avatar_size[0], avatar_offset[1] + avatar_size[1]),
        image=avatar,
        outline=(65, 65, 65),
        width=3
    )
    
    canvas.rounded_rectangle(
        (
            xp_offset[0] - xp_size[0],
            xp_offset[1] - xp_size[1],
        ),
        xp_size,
        radius=8,
        alpha=panel_alpha,
        fill="#000000",
        filters=[
            BlurBehind()
        ]
    )
    canvas.rounded_rectangle(
        (
            xp_offset[0] - xp_size[0] + 5,
            xp_offset[1] - 40 - 5,
        ),
        (
            xp_size[0] - 10,
            40
        ),
        radius=6,
        fill=(dominant_color[0] // 2, dominant_color[1] // 2, dominant_color[2] // 2),
        outline=(65, 65, 65),
        width=3
    )
    canvas.rounded_rectangle(
        (
            xp_offset[0] - xp_size[0] + 5 + 3,
            xp_offset[1] - 40 - 5 + 3,
        ),
        (
            xp_size[0] - 10 - 5,
            40 - 5
        ),
        radius=5,
        fill=dominant_color,
        crop=(
            0,
            0,
            int(xp_size[0] * (xp_amount / (total_xp - prev_total))),
            xp_size[1]
        )
    )
    canvas.text(
        (
            xp_offset[0] - xp_size[0] + 5,
            xp_offset[1] - xp_size[1] + 5
        ),
        format_number(int(xp)),
        24,
        bold=True,
        fill="#ffffff"
    )
    canvas.text(
        (
            xp_offset[0] - xp_size[0] + 10 + canvas.bound_width(xp_bounds),
            xp_offset[1] - xp_size[1] + 5 +
                canvas.bound_height(xp_bounds) -
                canvas.bound_height(xp_total_bounds)
        ),
        f"/{format_number(int(total_xp))}",
        18,
        bold=True,
        fill=(215, 215, 215)
    )
    
    canvas.rounded_rectangle(
        name_offset,
        (abs(name_bounds[0] - name_bounds[2]), abs(name_bounds[1] - name_bounds[3])),
        radius=8,
        alpha=panel_alpha,
        fill="#000000",
        filters=[
            BlurBehind()
        ]
    )
    canvas.text(
        name_center,
        name,
        32,
        bold=True,
        anchor="mm",
        fill="#ffffff"
    )
    
    canvas.rounded_rectangle(
        (
            bound_start[0] - text_padding,
            bound_start[1] - text_padding,
        ),
        bound_size,
        radius=8,
        alpha=panel_alpha,
        fill="#000000",
        filters=[
            BlurBehind()
        ]
    )
    canvas.text(
        (bound_start[0], bound_bottom),
        "Rank",
        26,
        anchor="lb",
        fill="#ffffff"
    )
    canvas.text(
        (bound_start[0] + canvas.bound_width(rl_bounds), bound_bottom),
        f"#{format_number(rank)}",
        32,
        anchor="lb",
        bold=True,
        fill="#ffd700"
    )
    canvas.text(
        (
            bound_start[0] +
            canvas.bound_width(rl_bounds) +
            canvas.bound_width(rank_bounds),
            bound_bottom
        ),
        "Level",
        26,
        anchor="lb",
        fill="#ffffff"
    )
    canvas.text(
        (
            bound_start[0] +
            canvas.bound_width(rl_bounds) +
            canvas.bound_width(rank_bounds) +
            canvas.bound_width(ll_bounds),
            bound_bottom
        ),
        format_number(level),
        32,
        anchor="lb",
        bold=True,
        fill="#ffd700"
    )
    
    if leveled_up:
        canvas.text(
            (
                xp_offset[0] - 5,
                xp_offset[1] - xp_size[1] + 5
            ),
            "LEVEL UP!",
            18,
            bold=True,
            italic=True,
            fill="#ffd700",
            anchor="ra"
        )
    
    return canvas.save_b64()

def get_level(xp: int):
    return (xp < 0 and -math.ceil(math.sqrt(abs(xp))) or math.floor(math.sqrt(abs(xp)))) + 1

def get_xp(level: int):
    return level < 0 and -math.pow(level - 1, 2) or math.pow(level - 1, 2)