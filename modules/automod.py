import math
from core.checks import listener, is_module_enabled, user_has_permissions
from database import DBConnection, loadQuery, resultExists
from core.embeds import EMBED_FILTERED, EMBED_STANDARD
from lingua import Language, LanguageDetectorBuilder
from humanfriendly import format_timespan
from guilded.ext import commands, tasks
from better_profanity import Profanity
from unidecode import unidecode
from datetime import timedelta
from bs4 import BeautifulSoup
from base import BOT_VERSION
from zipfile import ZipFile

import filters.evaluation as filter
import mimetypes
import requests
import guilded
import asyncio
import config
import csv
import io
import re
import os

SERVER_INVITE_REGEX = r"(?:https?:\/\/)?(?:www\.)?(discord\.gg|discordapp\.com\/invite|guilded\.gg|guilded\.com|guilded\.gg\/i|guilded\.com\/i)\/([\w/-]+)"
API_KEY_REGEXES = [
    r"gapi_([a-zA-Z0-9+\/]{86})==",
]
WHITELISTED_DOMAINS = ["https://media.tenor.com/"]
USER_AGENT = f"Server Guard/{BOT_VERSION} (Automod)"
LDNOOBW_LANGS = [
    "ar", "zh", "cs", "da", "nl", "en", "eo", "fil",
    "fi", "fr", "fr-Ca-u-sd-caqc", "de", "hi", "hu",
    "it", "ja", "kab", "tlh", "ko", "no", "fa", "pl",
    "pt", "ru", "es", "sv", "th", "tr",
]
LANGS = [
    Language.ARABIC, Language.CZECH, Language.DANISH, Language.DUTCH,
    Language.ENGLISH, Language.ESPERANTO, Language.FINNISH, Language.FRENCH,
    Language.GERMAN, Language.HINDI, Language.HUNGARIAN, Language.ITALIAN,
    Language.JAPANESE, Language.KOREAN, Language.PERSIAN, Language.POLISH,
    Language.PORTUGUESE, Language.RUSSIAN, Language.SPANISH, Language.SWEDISH,
    Language.THAI, Language.TURKISH,
]
LANG_MAP = {
    "ARABIC": "ar", "CZECH": "cs", "DANISH": "da", "DUTCH": "nl",
    "ENGLISH": "en", "ESPERANTO": "eo", "FINNISH": "fi", "FRENCH": "fr",
    "GERMAN": "de", "HINDI": "hi", "HUNGARIAN": "hu", "ITALIAN": "it",
    "JAPANESE": "ja", "KOREAN": "ko", "PERSIAN": "fa", "POLISH": "pl",
    "PORTUGUESE": "pt", "RUSSIAN": "ru", "SPANISH": "es", "SWEDISH": "sv",
    "THAI": "th", "TURKISH": "tr",
}

def get_cooldown_key(message: guilded.ChatMessage):
    return (message.author.id, message.channel.id)

class Automod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.spam_cooldowns = {}
        self.malicious_urls = []
        self.guilded_paths = []
        self.default_profanity_checks = {}
        self.guild_profanity_checks = {}
        self.language_detector = LanguageDetectorBuilder.from_languages(*LANGS).build()
        self.filters_ready = False

        asyncio.create_task(self.__load_profanities())
        asyncio.create_task(self.__load_guild_profanities())
        asyncio.create_task(self.__prepare_filters())
    
    def __get_content(self, message):
        content = [""]
        if isinstance(message, guilded.ChatMessage) or\
            isinstance(message, guilded.ForumTopicReply) or\
            isinstance(message, guilded.DocReply) or\
            isinstance(message, guilded.CalendarEventReply):
            content = [message.content or ""]
        elif isinstance(message, guilded.ForumTopic):
            content = [message.content or "", message.title or ""]
        elif isinstance(message, guilded.Media):
            content = [message.description]
        return content
    
    async def __prepare_filters(self):
        import filters.config as filter_config
        if not os.path.exists(filter_config.MODEL_LOC):
            import filters.training as training
            training.execute()
            self.rnn_model = filter._load_model()
        else:
            self.rnn_model = filter._load_model()
        self.filters_ready = True
        print("Automod filters ready")
    
    async def __load_guild_profanities(self):
        print("Loading Guild Profanity objects")
        async with DBConnection() as db:
            for server in self.bot.servers:
                try:
                    response = await db.query(loadQuery("getGuild"), {"id": server.id})
                except:
                    continue
                else:
                    if resultExists(response):
                        data = response[0]["result"][0]
                        blacklist = data.get("filter_blacklist", [])
                        if len(blacklist) > 0:
                            print(f"Generating Profanity object for server '{server.name}'")
                            self.guild_profanity_checks[server.id] = Profanity(blacklist)
                            print(f"Profanity object for server '{server.name}' generated")
        print("Guild Profanity objects loaded")
    
    async def __load_profanities(self):
        print("Loading default Profanity objects")
        for lang in LDNOOBW_LANGS:
            url = f"https://raw.githubusercontent.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/{lang}"
            cached = None
            profanities = None
            if os.path.exists(f"/tmp/profanities-{lang}"):
                try:
                    cached = open(f"/tmp/profanities-{lang}", "r")
                except:
                    pass

            if cached:
                profanities = cached.read().splitlines()
            else:
                try:
                    response = requests.get(url)
                    if response.ok:
                        profanities = response.text.splitlines()
                        with open(f"/tmp/profanities-{lang}", "w") as f:
                            f.write(response.text)
                except:
                    pass
            if profanities:
                print(f"Generating Profanity object for lang '{lang}'")
                self.default_profanity_checks[lang] = Profanity(profanities)
                print(f"Profanity object for lang '{lang}' generated")
        print("Default Profanity objects loaded")
    
    async def was_message_automoderated(self, message: guilded.ChatMessage):
        while getattr(message, "automoderated", None) is None:
            await asyncio.sleep(0.1)
        return message.automoderated
    
    async def apply_heat(self, member: guilded.Member, violation: str):
        pass
    
    async def notify_filter(self, message, reason: str):
        if isinstance(message, guilded.ChatMessage):
            await message.reply(embed=EMBED_FILTERED(
                message.author,
                reason
            ), private=True)
        message.automoderated = True
    
    async def send_log(self, channel: guilded.ChatChannel, message: guilded.ChatMessage, content: str, filter: str, extraData: dict = {}):
        if not channel: return
        user = message.author
        # TODO: Display user heat in embed
        if extraData.get("redact"):
            for item in extraData["redact"]:
                content = content.replace(item, "[REDACTED]")
        em = EMBED_STANDARD(
            title=f"{filter} Filter Triggered",
            description=content,
            url=message.share_url,
        )
        em.set_thumbnail(user.display_avatar.url)
        em.add_field(name="Author", value=user.mention, inline=True)
        if extraData.get("certainty"):
            from base import BOT_VERSION
            em.set_footer(text=f"v{BOT_VERSION} {str.capitalize(config.DATABASE_DB)} • Certainty: {extraData['certainty']}%")
        if extraData.get("filtered"):
            em.add_field(name="Filtered Message", value=extraData["filtered"], inline=False)
        if extraData.get("threat"):
            em.add_field(name="Threat Category", value=extraData["threat"])
        if extraData.get("invite"):
            em.add_field(name="Invite Link", value=extraData["invite"])
        await channel.send(embed=em, silent=True)
    
    async def filter_message(self, message):
        if not getattr(message, "server", False): return
        if not getattr(message, "channel", False): return
        if not getattr(message, "author", False): return
        if message.author.bot: return
        if self.filters_ready:
            import filters.config as filter_config
            print(f"Will try filtering content: \"{message.content}\"")
            prediction = filter.predict(message.content, self.rnn_model)
            print(f'"{message.content}": {prediction}')
            test_log_channel: guilded.ChatChannel = await self.bot.getch_channel("2c1b9704-79a5-48d0-9925-6e47aaa04d67")
            em = EMBED_STANDARD(
                title=f"Message from {message.author.mention}",
                description=message.content,
                url=message.share_url,
            ).set_thumbnail(url=message.author.display_avatar.url)
            for label in filter_config.DETECTION_CLASSES:
                em.add_field(name=label.replace("_", " ").title(), value=str(math.floor(prediction[label] * 100)))
            await test_log_channel.send(embed=em, silent=True)
        if await user_has_permissions(message.author, bypass_filter=True): return
        async with DBConnection() as db:
            try:
                response = await db.query(loadQuery("getGuild"), {"id": message.server.id})
            except:
                return
            else:
                if resultExists(response):
                    data = response[0]["result"][0]
                    log_channel_id = data.get("logs_automod")
                    log_channel = None
                    if log_channel_id:
                        try:
                            log_channel = await self.bot.getch_channel(log_channel_id)
                        except:
                            pass
                    spam_amt = data.get("spam_filter")
                    if spam_amt and spam_amt > 0:
                        guild_spam_cooldown = self.spam_cooldowns.get(message.server.id)
                        if not guild_spam_cooldown:
                            guild_spam_cooldown = commands.CooldownMapping.from_cooldown(spam_amt, 60, get_cooldown_key)
                            self.spam_cooldowns[message.server.id] = guild_spam_cooldown
                        if guild_spam_cooldown.update_rate_limit(message):
                            await message.delete()
                            for msg in await message.channel.history(after=message.created_at - timedelta(minutes=1, seconds=30)):
                                if msg.author.id == message.author.id:
                                    await msg.delete()
                            await self.notify_filter(message, "Talking too fast!")
                            await self.send_log(log_channel, message, self.__get_content(message)[0], "Spam")
                            return
                    _content = self.__get_content(message)
                    for content in _content:
                        print(f"Scanning '{content}'")
                        default_profanities = data.get("default_profanities", [])
                        if len(default_profanities) > 0:
                            for result in self.language_detector.detect_multiple_languages_of(content):
                                code = LANG_MAP.get(result.language.name)
                                print(f"Detected language '{code}'")
                                if code and code in default_profanities:
                                    profanity_check: Profanity = self.default_profanity_checks.get(code)
                                    if profanity_check:
                                        contains = profanity_check.contains_profanity(content)
                                        if contains:
                                            await message.delete()
                                            await self.notify_filter(message, "Profanity Detected")
                                            await self.send_log(log_channel, message, content, "Profanity", {"filtered": profanity_check.censor(content)})
                                            return
                        if data.get("malicious_urls", False):
                            for url in self.malicious_urls.keys():
                                if url in content:
                                    await message.delete()
                                    await self.notify_filter(message, "Malicious URL!")
                                    await self.send_log(log_channel, message, content, "Malicious URL", {"threat": self.malicious_urls[url]})
                                    return
                        if data.get("filter_invites", False):
                            for domain, invite in re.findall(SERVER_INVITE_REGEX, content):
                                lowered: str = invite.lower()
                                stop = False
                                for path in self.guilded_paths:
                                    if path in lowered:
                                        stop = True
                                        break
                                if "guilded" in domain and lowered == message.server.slug.lower(): continue # Don't filter invite links to their own server lol
                                if stop: continue
                                await message.delete()
                                await self.notify_filter(message, "Invite Link")
                                await self.send_log(log_channel, message, content, "Invite Link", {"invite": f"https://www.{domain}/{invite}"})
                                break
                        if data.get("filter_api_keys", False):
                            for regex in API_KEY_REGEXES:
                                match = re.match(regex, content)
                                if match:
                                    await message.delete()
                                    await self.notify_filter(message, content, "API Key Detected", {
                                        "redact": [match.group(0)]
                                    })
                                    await self.send_log(log_channel, message, content, "API Key")
                                    return
                        if len(data.get("untrusted_block_attachments", [])) > 0:
                            is_trusted = await user_has_permissions(message.author, is_trusted=True)
                            if not is_trusted:
                                block_message = False
                                blocked_type = None
                                for _, link in re.findall(r'\[(.*?)\]\((.*?)\)', content):
                                    link: str
                                    stripped_link = link
                                    if '?' in stripped_link:
                                        stripped_link = stripped_link.split('?')[0]
                                    is_whitelisted = False
                                    for wl in WHITELISTED_DOMAINS:
                                        if link.startswith(wl) and not '@' in link:
                                            is_whitelisted = True
                                            break
                                    if is_whitelisted: continue
                                    mimeType = mimetypes.guess_type(stripped_link)
                                    if mimeType[0]:
                                        for t in data.get("untrusted_block_attachments", []):
                                            t: str
                                            if mimeType[0].startswith(t):
                                                block_message = True
                                                blocked_type = t.capitalize()
                                                break
                                    else:
                                        head_resp: requests.Response = await requests.head(link, headers={
                                            "user-agent": USER_AGENT,
                                        })
                                        if head_resp.ok:
                                            content_type = head_resp.headers.get("content-type")
                                            content_disposition = head_resp.headers.get("content-disposition")
                                            dis_mimeType = mimetypes.guess_type(content_disposition)
                                            if "html" in content_type:
                                                page_resp: requests.Response = await requests.get(link, headers={
                                                    "user-agent": USER_AGENT,
                                                })
                                                if page_resp.ok:
                                                    parsed = BeautifulSoup(page_resp.text)
                                                    if "image" in data["untrusted_block_attachments"]:
                                                        is_image = False
                                                        for tag in parsed('meta', attrs={'property': ['og:image', 'twitter:image', 'twitter:image:src']}):
                                                            is_image = True
                                                        for tag in parsed('meta', attrs={'property': ['og:type']}):
                                                            og_type: str = tag['content'].lower().strip()
                                                            if og_type.startswith(('article', 'website', 'book', 'profile', 'video', 'music')):
                                                                is_image = False
                                                                for tag in parsed('meta', attrs={'property': ['og:description']}):
                                                                    desc: str = tag['content'].lower().strip()
                                                                    if 'screenshot' in desc or '':
                                                                        is_image = False
                                                                for tag in parsed('meta', attrs={'name': ['description']}):
                                                                    desc: str = tag['content'].lower().strip()
                                                                    if 'screenshot' in desc or '':
                                                                        is_image = False
                                                                for tag in parsed('meta', attrs={'name': ['keywords']}):
                                                                    keywords: str = tag['content'].lower()
                                                                    if 'photo' in keywords or 'image upload' in keywords or 'image hosting' in keywords:
                                                                        is_image = True
                                                                    if 'video' in keywords or not 'image' in keywords:
                                                                        is_image = False
                                                        if is_image:
                                                            block_message = True
                                                            blocked_type = "Image"
                                                    if "video" in data["untrusted_block_attachments"] and not block_message:
                                                        is_video = False
                                                        for tag in parsed('meta', attrs={'property': ['og:type']}):
                                                            og_type: str = tag['content'].lower().strip()
                                                            if og_type.startswith(('video')):
                                                                is_video = True
                                                        if is_video:
                                                            block_message = True
                                                            blocked_type = "Video"
                                                    if "audio" in data["untrusted_block_attachments"] and not block_message:
                                                        is_audio = False
                                                        for tag in parsed('meta', attrs={'property': ['og:type']}):
                                                            og_type: str = tag['content'].lower().strip()
                                                            if og_type.startswith(('music')):
                                                                is_audio = True
                                                        if is_audio:
                                                            block_message = True
                                                            blocked_type = "Audio"
                                            else:
                                                for t in data["untrusted_block_attachments"]:
                                                    t: str
                                                    if content_type.startswith(t):
                                                        block_message = True
                                                        blocked_type = t.capitalize()
                                                        break
                                                    else:
                                                        if dis_mimeType[0]:
                                                            if dis_mimeType[0].startswith(t):
                                                                block_message = True
                                                                blocked_type = t.capitalize()
                                                                break
                                if block_message:
                                    await message.delete()
                                    await self.notify_filter(message, f"Untrusted Attachment ({blocked_type})")
                                    await self.send_log(log_channel, message, content, "Untrusted Attachment", {"attachment_type": blocked_type})
                                    return

    async def refresh_filter(self, guild_id: str, profanities: list=None):
        if profanities is None:
            async with DBConnection() as db:
                try:
                    response = await db.query(loadQuery("getGuild"), {"id": guild_id})
                except:
                    return
                else:
                    if resultExists(response):
                        data = response[0]["result"][0]
                        profanities = data.get("profanities", [])
        
        if len(profanities) > 0:
            self.guild_profanity_checks[guild_id] = Profanity(profanities)
        else:
            if self.guild_profanity_checks.get(guild_id):
                del self.guild_profanity_checks[guild_id]
                self.guild_profanity_checks[guild_id] = None
    
    @commands.Cog.listener()
    async def on_bot_add(self, event: guilded.BotAddEvent):
        await self.refresh_filter(event.server.id)
    
    @commands.Cog.listener()
    async def on_bot_remove(self, event: guilded.BotRemoveEvent):
        if self.guild_profanity_checks.get(event.server.id):
            del self.guild_profanity_checks[event.server.id]
            self.guild_profanity_checks[event.server.id] = None
    
    @commands.Cog.listener()
    async def on_message(self, event: guilded.MessageEvent):
        event.message.automoderated = False

        if await is_module_enabled("automod", event):
            await self.filter_message(event.message)
    
    @listener("automod")
    @commands.Cog.listener()
    async def on_message_update(self, event: guilded.MessageUpdateEvent):
        await self.filter_message(event.message)
    
    @commands.Cog.listener()
    async def on_calendar_event_reply_create(self, event: guilded.CalendarEventReplyCreateEvent):
        event.reply.automoderated = False

        if await is_module_enabled("automod", event):
            await self.filter_message(event.reply)
    
    @listener("automod")
    @commands.Cog.listener()
    async def on_calendar_event_reply_update(self, event: guilded.CalendarEventReplyUpdateEvent):
        await self.filter_message(event.reply)
    
    @commands.Cog.listener()
    async def on_doc_reply_create(self, event: guilded.DocReplyCreateEvent):
        event.reply.automoderated = False

        if await is_module_enabled("automod", event):
            await self.filter_message(event.reply)
    
    @listener("automod")
    @commands.Cog.listener()
    async def on_doc_reply_update(self, event: guilded.DocReplyUpdateEvent):
        await self.filter_message(event.reply)
    
    @commands.Cog.listener()
    async def on_forum_topic_reply_create(self, event: guilded.ForumTopicReplyCreateEvent):
        event.message.automoderated = False

        if await is_module_enabled("automod", event):
            await self.filter_message(event.reply)
    
    @listener("automod")
    @commands.Cog.listener()
    async def on_forum_topic_reply_update(self, event: guilded.ForumTopicReplyUpdateEvent):
        await self.filter_message(event.reply)
    
    @commands.Cog.listener()
    async def on_bot_remove(self, event: guilded.BotRemoveEvent):
        if self.spam_cooldowns.get(event.server.id):
            del self.spam_cooldowns[event.server.id]
    
    @tasks.loop(minutes=30)
    async def refresh_cache(self):
        # Malicious URLs
        try:
            response = await requests.get('https://urlhaus.abuse.ch/downloads/csv/')
            zip = ZipFile(io.BytesIO(response.content))
            item = zip.open("csv.txt")
            reader = csv.reader(io.TextIOWrapper(item, "utf-8"))
        except Exception as e:
            print(f"Failed to refresh malicious URLs: {'{}: {}'.format(type(e).__name__, e)}")
        else:
            self.malicious_urls.clear()
            for row in reader:
                if len(row) < 2 or ("id" in row[0]): continue
                url = row[2]
                threat = row[5]
                self.malicious_urls[url] = threat
            print("Refreshed malicious URLs")
        # Guilded Paths
        try:
            response = await requests.get("https://www.guilded.gg/sitemap_landing.xml")
            soup = BeautifulSoup(response.text, "xml")
        except Exception as e:
            print(f"Failed to refresh Guilded Paths: {'{}: {}'.format(type(e).__name__, e)}")
        else:
            self.guilded_paths.clear()
            for tag in soup.find_all("url"):
                loc = tag.loc
                if loc:
                    self.guilded_paths.append(loc.string[23:].lower())
            print("Refreshed Guilded Paths")

def setup(bot: commands.Bot):
    bot.add_cog(Automod(bot))