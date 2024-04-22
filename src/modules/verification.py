from core.embeds import EMBED_STANDARD, EMBED_FILTERED
from core.checks import listener, is_module_enabled
from core.images import IMAGE_DEFAULT_AVATAR
from werkzeug.exceptions import BadRequest
from quart_rate_limiter import rate_limit
from quart import Quart, jsonify, request
from humanfriendly import format_timespan
from datetime import datetime, timedelta
from guilded.ext import commands, tasks
from Crypto.Util.Padding import unpad
from modules.welcomer import Welcomer
from modules.automod import Automod
from quart_cors import route_cors
from Crypto.Cipher import AES

import database as db
import requests
import hashlib
import guilded
import base64
import config

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.tor_exit_nodes = []
        self.update_exit_nodes.start()
    
    async def generate_token(self, member: guilded.Member):
        try:
            token = await db.auth.create_verify_token(member.id, member.server.id)
        except db.DatabaseError as e:
            print("Failed to generate token: {} - {}".format(type(e).__name__, e))
            return None
        else:
            return token.id
    
    async def get_token(self, token: str):
        try:
            token = await db.auth.get_token(token)
        except db.DatabaseError as e:
            print("Failed to get token: {} - {}".format(type(e).__name__, e))
            return None
        else:
            if token.type != "verify":
                return None
            else:
                return token
    
    async def start_verification(self, channel: guilded.ChatChannel, author: guilded.Member):
        token = await self.generate_token(author)
        
        em = EMBED_STANDARD(
            title="Verification",
            description=f"Here's your verification link, {author.mention}!"
        ) \
            .add_field(name="Link", value=f"{config.ORIGIN_SITE}/verify/{token}")
        
        await channel.send(embed=em, private=True)
    
    def validate_turnstile(self, response: str, user_ip: str):
        turnstile_response = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={
                "secret": config.TURNSTILE_SECRET,
                "response": response,
                "remoteip": user_ip,
            }
        )
        
        return turnstile_response.ok
    
    @tasks.loop(minutes=1)
    async def update_exit_nodes(self):
        response = requests.get("https://www.dan.me.uk/torlist/?exit")
        if response.ok:
            self.tor_exit_nodes = response.text.splitlines()
    
    @commands.command()
    @module("verification")
    async def verify(self, ctx: commands.Context):
        try:
            guild = await db.servers.fetch_or_create_server(ctx.server)
        except:
            return
        else:
            roles = ctx.author._role_ids
            if len(roles) == 0:
                try:
                    roles = await ctx.author.fetch_role_ids()
                except:
                    raise commands.CommandError

            verified_role = guild.settings.get("verified_role")
            unverified_role = guild.settings.get("unverified_role")
            
            is_verified = False
            if unverified_role:
                if int(unverified_role) not in roles:
                    is_verified = True
            if verified_role:
                if int(verified_role) in roles:
                    is_verified = True
                else:
                    is_verified = False
            
            if is_verified:
                raise commands.CommandError("You are already verified!")
            else:
                await self.start_verification(ctx.channel, ctx.author)
                await ctx.message.delete()
    
    @listener("verification")
    @commands.Cog.listener()
    async def on_message_reaction_add(self, event: guilded.MessageReactionAddEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            return
        else:
            verification_channel = guild.settings.get("verification_channel")
            if verification_channel and event.channel_id == verification_channel:
                if event.emote.id == 90002171:
                    await self.start_verification(event.channel, event.member)
    
    @listener("verification")
    @commands.Cog.listener()
    async def on_message(self, event: guilded.MessageEvent):
        try:
            guild = await db.servers.fetch_or_create_server(event.server)
        except:
            return
        else:
            verification_channel = guild.settings.get("verification_channel")
            if verification_channel and event.message.channel_id == verification_channel:
                if event.message.content.lower().strip() != "/verify":
                    await event.message.reply(
                        embed=EMBED_FILTERED(event.message.author, "Only /verify can be sent in the verification channel")
                    )
                    await event.message.delete()
    
    @listener("verification")
    @commands.Cog.listener()
    async def on_member_join(self, event: guilded.MemberJoinEvent):
            try:
                guild = await db.servers.fetch_or_create_server(event.server)
            except:
                return
            else:
                verification_channel = guild.settings.get("verification_channel")
                unverified_role = guild.settings.get("unverified_role")
                
                if unverified_role:
                    try:
                        await event.member.add_role(guilded.Object(unverified_role))
                    except:
                        pass
                
                if verification_channel:
                    try:
                        verification_channel = await self.bot.getch_channel(verification_channel)
                    except:
                        pass
                    
                    links = [
                        guilded.utils.link("https://www.guilded.gg/server-guard", "Support Server"),
                        guilded.utils.link("https://serverguard.xyz", "Website"),
                        guilded.utils.link("https://www.guilded.gg/b/2b2fa670-37c9-453c-8b35-5473fe932e6f", "Invite")
                    ]
                    
                    em = EMBED_STANDARD(
                        title="Verification",
                        description=f"Welcome {event.member.mention}! Please click the :white_check_mark: below to start verification!\n\n*Alternatively, you can use `/verify` if you are having issues."
                    )
                    em.add_field(
                        name="Links",
                        value=" • ".join(links)
                        #"Support Server • Website • Invite"
                    )
                    
                    message: guilded.ChatMessage = await verification_channel.send(embed=em)
                    try:
                        await message.add_reaction(guilded.Object(90002171))
                    except Exception as e:
                        print(f"Failed to add reaction: {e}")
    
    def register_routes(self, app: Quart):
        @app.route("/verify/<string:id>", methods=["GET"])
        @route_cors(allow_headers=["content-type"], allow_methods=["GET"], allow_origin=["*"])
        async def GetVerification(id: str):
            token = await self.get_token(id)
            if token:
                guild = await self.bot.getch_server(token.guild_id)
                user = await self.bot.getch_user(token.user_id)
                
                return jsonify({
                    "user": {
                        "name": user.display_name,
                        "avatar": user.display_avatar.url,
                    },
                    "guild": {
                        "name": guild.name,
                        "avatar": guild.icon and guild.icon.url or IMAGE_DEFAULT_AVATAR,
                    }
                }), 200
            else:
                return jsonify({"error": "Invalid token"}), 404
        
        @app.route("/verify/<string:id>", methods=["POST"])
        @route_cors(allow_headers=["content-type"], allow_methods=["POST"], allow_origin=["*"])
        @rate_limit(3, timedelta(minutes=1))
        async def StartVerification(id: str):
            body = request.get_data(as_text=True)
            enc = base64.b64decode(body)
            cipher = AES.new(config.SITE_ENCRYPTION.encode('utf-8'), AES.MODE_ECB)
            try:
                post_data = decoder.decode(unpad(cipher.decrypt(enc), 16).decode('utf-8'))
            except Exception as e:
                raise BadRequest
            
            browser_id = post_data.get('bi')
            using_vpn = post_data.get('v') != '0'
            turnstile = post_data.get('cf')
            
            user_ip = request.remote_addr
            if request.headers.get("CF-Connecting-IP"):
                user_ip = request.headers.get("CF-Connecting-IP")
            elif request.headers.get("X-Forwarded-For"):
                user_ip = request.headers.get("X-Forwarded-For").split(",")[0]
            
            hashed_ip = hashlib.sha256(user_ip.encode('utf-8')).hexdigest()
            
            token = await self.get_token(id)
            if token:
                try:
                    guild = await db.servers.fetch_server(token.guild_id)
                except:
                    return jsonify({"error": "Guild not found"}), 404
                else:
                    try:
                        user = await guild.fetch_member(token.user_id)
                    except:
                        return jsonify({"error": "User not found"}), 404
                    
                    try:
                        identifier = await db.users.fetch_identifier(token.user_id)
                    except Exception as e:
                        print(e)
                        identifier = None

                    logs_channel = guild.settings.get("logs_verify")
                    is_premium = guild.settings.get("premium")[0] == "1"
                    
                    verified_role = guild.settings.get("verified_role")
                    unverified_role = guild.settings.get("unverified_role")
                    
                    bot_server = await self.bot.getch_server(token.guild_id)
                    guild_user = await bot_server.getch_member(token.user_id)
                    
                    async def update_id():
                        try:
                            await identifier.update(
                                vpn=using_vpn,
                                hashed_ip=hashed_ip,
                                browser_id=browser_id
                            )
                        except Exception as e:
                            print(e)
                            pass
                    
                    async def accept():
                        try:
                            await token.delete()
                        except:
                            pass
                        
                        await update_id()
                        
                        if logs_channel:
                            em = EMBED_STANDARD(
                                title=f"{guild_user.mention}'s evaluation",
                                colour=guilded.Colour.green()
                            )
                            em.add_field(
                                "Account Age",
                                format_timespan((datetime.now() - guild_user.created_at).timestamp())
                            )
                            em.add_field(
                                "VPN",
                                "Yes" if using_vpn else "No"
                            )

                            em.add_field(
                                "Passed",
                                "Yes"
                            )
                            em.set_thumbnail(url=guild_user.display_avatar.url)
                            await logs_channel.send(embed=em)
                        
                        if verified_role:
                            try:
                                await guild_user.add_role(guilded.Object(verified_role))
                            except:
                                pass
                        
                        if unverified_role:
                            try:
                                await guild_user.remove_role(guilded.Object(unverified_role))
                            except:
                                pass
                        
                        if await is_module_enabled("welcomer", guild_user):
                            welcomer: Welcomer = self.bot.get_cog("Welcomer")
                            await welcomer.welcome_member(guild_user)
                        
                        return jsonify({"status": "accepted"}), 200
                    
                    async def reject(translation_string: str):
                        try:
                            await token.delete()
                        except:
                            pass
                        
                        await update_id()

                        if logs_channel:
                            em = EMBED_STANDARD(
                                title=f"{guild_user.mention}'s evaluation",
                                colour=guilded.Colour.red()
                            )
                            em.add_field(
                                name="Account Age",
                                value=format_timespan((datetime.now() - guild_user.created_at).timestamp())
                            )
                            if guild_user.joined_at:
                                em.add_field(
                                    name="Joined",
                                    value=format_timespan((datetime.now() - guild_user.joined_at).timestamp())
                                )
                            em.add_field(
                                "VPN",
                                "Yes" if using_vpn else "No"
                            )

                            em.add_field(
                                "Passed",
                                "No"
                            )
                            # TODO: Translate reason once localization is implemented
                            em.add_field(
                                "Reason",
                                translation_string
                            )
                            em.set_thumbnail(url=guild_user.display_avatar.url)
                            await logs_channel.send(embed=em)
                        
                        return jsonify({"status": "rejected", "reason": translation_string}), 200
                    
                    if resultExists(user_response):
                        if user_response[0]["result"][0]["bypass_verification"]:
                            return await accept()
                    
                    if not verify_browseragent(request.user_agent.string):
                        return await reject("invalid_browser")

                    admin_contact = guild.settings.get("admin_contact", "")

                    block_tor = guild.settings.get("block_tor", False)
                    proxy_check = guild.settings.get("check_ips", True)
                    
                    re_toxicity = guild.settings.get("re_toxicity", 0)
                    re_hatespeech = guild.settings.get("re_hatespeech", 0)
                    re_nsfw = guild.settings.get("re_nsfw", 0)
                    re_blacklist = guild.settings.get("re_blacklist", [])
                    
                    threat_score = int(request.headers.get("X-Threat-Score", 0))
                    
                    if guild.is_premium and proxy_check:
                        if threat_score >= 50:
                            return await reject("proxy_check")
                    
                    if block_tor and user_ip in self.tor_exit_nodes:
                        return await reject("tor")
                    
                    if re_toxicity > 0 or re_hatespeech > 0:
                        automod: Automod = self.bot.get_cog("Automod")
                        for item in [guild_user.name, guild_user.bio]:
                            toxicity, hatespeech = automod.apply_filters(item)
                            if re_toxicity > 0 and toxicity >= re_toxicity:
                                return await reject("toxicity")
                            if re_hatespeech > 0 and hatespeech >= re_hatespeech:
                                return await reject("hatespeech")
                    
                    if guild.is_premium and guild.settings.get("filter_nsfw", 0) > 0:
                        urls = {
                            "banner": guild_user.banner and guild_user.banner.url or None,
                            "avatar": guild_user.display_avatar.url
                        }
                        for field, url in urls.items():
                            if url:
                                nudity = round(automod.scan_nsfw(url=url) * 100)
                                if nudity >= guild.settings.get("filter_nsfw", 0):
                                    return await reject("nsfw")
                    
                    if turnstile:
                        if not self.validate_turnstile(turnstile, user_ip):
                            return await reject("turnstile")
                    else:
                        return await reject("turnstile_missing")
                    
                    try:
                        banned_users = await guild.get_banned_members()
                    except Exception as e:
                        print("Failed to get banned members: {} - {}".format(type(e).__name__, e))
                        return await reject("internal_error")
                    
                    try:
                        matching_identifiers = await ident
                    except Exception as e:
                        print("Failed to get matching identifiers: {} - {}".format(type(e).__name__, e))
                        return await reject("internal_error")
                    
                    if resultExists(matching_response):
                        return await reject("linked_account")
                    
                    return await accept()

def setup(bot: commands.Bot):
    bot.add_cog(Verification(bot))

browser_useragents = \
    [
        "ABrowse", "Acoo Browser", "America Online Browser", "AmigaVoyager", "AOL", "Arora",
        "Avant Browser", "Beonex", "BonEcho", "Browzar", "Camino", "Charon", "Cheshire",
        "Chimera", "Chrome", "ChromePlus", "Classilla", "CometBird", "Comodo_Dragon",
        "Conkeror", "Crazy Browser", "Cyberdog", "Deepnet Explorer", "DeskBrowse", "Dillo",
        "Dooble", "Edge", "Element Browser", "Elinks", "Enigma Browser", "EnigmaFox",
        "Epiphany", "Escape", "Firebird", "Firefox", "Fireweb Navigator", "Flock", "Fluid",
        "Galaxy", "Galeon", "GranParadiso", "GreenBrowser", "Hana", "HotJava", "IBM WebExplorer",
        "IBrowse", "iCab", "Iceape", "IceCat", "Iceweasel", "iNet Browser", "Internet Explorer",
        "iRider", "Iron", "K-Meleon", "K-Ninja", "Kapiko", "Kazehakase", "Kindle Browser", "KKman",
        "KMLite", "Konqueror", "LeechCraft", "Links", "Lobo", "lolifox", "Lorentz", "Lunascape",
        "Lynx", "Madfox", "Maxthon", "Midori", "Minefield", "Mozilla", "myibrow", "MyIE2",
        "Namoroka", "Navscape", "NCSA_Mosaic", "NetNewsWire", "NetPositive", "Netscape", "NetSurf",
        "OmniWeb", "Opera", "Orca", "Oregano", "osb-browser", "Palemoon", "Phoenix", "Pogo", "Prism",
        "QtWeb Internet Browser", "Rekonq", "retawq", "RockMelt", "Safari", "SeaMonkey", "Shiira",
        "Shiretoko", "Sleipnir", "SlimBrowser", "Stainless", "Sundance", "Sunrise", "surf", "Sylera",
        "Tencent Traveler", "TenFourFox", "theWorld Browser", "uzbl", "Vimprobable", "Vonkeror",
        "w3m", "WeltweitimnetzBrowser", "WorldWideWeb", "Wyzo", "Android Webkit Browser", "BlackBerry",
        "Blazer", "Bolt", "Browser for S60", "Doris", "Dorothy", "Fennec", "Go Browser", "IE Mobile",
        "Iris", "Maemo Browser", "MIB", "Minimo", "NetFront", "Opera Mini", "Opera Mobile", "SEMC-Browser",
        "Skyfire", "TeaShark", "Teleca-Obigo", "uZard Web", "Thunderbird", "AbiLogicBot", "Link Valet",
        "Link Validity Check", "LinkExaminer", "LinksManager.com_bot", "Mojoo Robot", "Notifixious",
        "online link validator", "Ploetz + Zeller", "Reciprocal Link System PRO", "REL Link Checker Lite",
        "SiteBar", "Vivante Link Checker", "W3C-checklink", "Xenu Link Sleuth", "EmailSiphon",
        "CSE HTML Validator", "CSSCheck", "Cynthia", "HTMLParser", "P3P Validator",
        "W3C_CSS_Validator_JFouffa", "W3C_Validator", "WDG_Validator", "Awasu", "Bloglines",
        "everyfeed-spider", "FeedFetcher-Google", "GreatNews", "Gregarius", "MagpieRSS", "NFReader",
        "UniversalFeedParser", "!Susie", "Amaya", "Cocoal.icio.us", "DomainsDB.net MetaCrawler", "gPodder",
        "GSiteCrawler", "iTunes", "lftp", "MetaURI", "MT-NewsWatcher", "Nitro PDF", "Snoopy",
        "URD-MAGPIE", "WebCapture", "Windows-Media-Player"
    ]

def verify_browseragent(useragent: str):
    if any(browser_useragent in useragent for browser_useragent in browser_useragents):
        return True
    return False