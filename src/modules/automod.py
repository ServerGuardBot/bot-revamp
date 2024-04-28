from core.checks import listener, is_module_enabled, user_has_permissions
from private_detector.inference import load_model, read_image
from core.embeds import EMBED_FILTERED, EMBED_STANDARD
from lingua import Language, LanguageDetectorBuilder
from database.permissions import UserPermissions
from guilded.utils import valid_video_extensions
from mdit_plain.renderer import RendererPlain
from humanfriendly import format_timespan
from guilded.ext import commands, tasks
from better_profanity import Profanity
from markdown_it import MarkdownIt
from nudenet import NudeDetector
from unidecode import unidecode
from datetime import timedelta
from typing import List, Tuple
from bs4 import BeautifulSoup
from base import BOT_VERSION
from threading import Thread
from zipfile import ZipFile

import filters.evaluation as filter
import tensorflow as tf
import database as db
import mimetypes
import requests
import guilded
import asyncio
import config
import uuid
import csv
import io
import re
import os

SERVER_INVITE_REGEX = r"(?:https?:\/\/)?(?:www\.)?(discord\.gg|discordapp\.com\/invite|guilded\.gg|guilded\.com|guilded\.gg\/i|guilded\.com\/i)\/([\w/-]+)"
API_KEY_REGEXES = [
    r"gapi_([a-zA-Z0-9+\/]{86})==",
]
WHITELISTED_DOMAINS = ["https://media.tenor.com/"]
USER_AGENT = config.USER_AGENT.format(BOT_VERSION, "Automod")
LDNOOBW_LANGS = [
    "ar", "cs", "da", "nl", "en", "eo",
    "fi", "fr", "de", "hi", "hu", "it",
    "ja", "ko", "fa", "pl", "pt", "ru",
    "es", "sv", "th", "tr",
] # "zh", "fr-Ca-u-sd-caqc", "no", "tlh", "fil", "kab"
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

ATTACHMENT_REGEX = re.compile(r'!\[(?P<caption>.+)?\]\((?P<url>(?:(?:https:\/\/(?:s3-us-west-2\.amazonaws\.com\/www\.guilded\.gg|img\.guildedcdn\.com|img2\.guildedcdn\.com|www\.guilded\.gg|cdn\.gilcdn\.com)\/(?:ContentMediaGenericFiles|ContentMedia|WebhookPrimaryMedia)\/[a-zA-Z0-9]+-Full)|(?:https:\/\/media\d+\.giphy\.com\/media\/[^ \n]+)|(?:https:\/\/media\.tenor\.com\/[^ \n]+))\.(?P<extension>webp|jpeg|jpg|png|gif|apng|webm|mp4)(?:\?.+)?)\)')

strip_md = MarkdownIt(renderer_cls=RendererPlain)

def _extract_attachments(_state, content: str):
    attachments = []

    matches: List[Tuple[str, str, str]] = re.findall(ATTACHMENT_REGEX, content)
    for match in matches:
        caption, url, extension = match
        attachment = guilded.Attachment(
            state=_state,
            data={
                'type': guilded.FileType.video if extension in valid_video_extensions else guilded.FileType.image,
                'caption': caption or None,
                'url': url,
            },
        )
        attachments.append(attachment)
    
    return attachments

def get_cooldown_key(message: guilded.ChatMessage):
    return (message.author.id, message.channel.id)

def weight_filters(filters: dict, positive_weights: dict, negative_weights: dict):
    new_filters = {}
    for filter_name, filter_value in filters.items():
        new_filters[filter_name] = filter_value * positive_weights[filter_name]
        for other_name, other_value in negative_weights.items():
            if not filters.get(other_name): continue
            new_filters[filter_name] = new_filters[filter_name] * (1 - (filters[other_name] * other_value))
    
    total_weights = 0
    for weight_value in new_filters.values():
        if weight_value > 0:
            total_weights += 1

    total = 0
    for filter_name, filter_value in new_filters.items():
        total += filter_value
    
    return new_filters, 0 if total_weights == 0 else total / total_weights

class Automod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.spam_cooldowns = {}
        self.malicious_urls = {}
        self.guilded_paths = []
        self.default_profanity_checks = {}
        self.guild_profanity_checks = {}
        self.language_detector = LanguageDetectorBuilder.from_languages(*LANGS).build()

        self.nude_detector = NudeDetector()
        print("Loaded Nude Detector")
        if config.LOAD_NSFW:
            self.nsfw_model = load_model()
            print("Loaded NSFW Model")

        self.filters_ready = False

        # self.bot.loop.create_task(self.__load_profanities())
        # self.bot.loop.create_task(self.__load_guild_profanities())
        # self.bot.loop.create_task(self.__prepare_filters())
    
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
        for server in await self.bot.fetch_servers():
            try:
                guild = await db.servers.fetch_or_create_server(server)
            except:
                continue
            else:
                blacklist = guild.settings.get("word_blacklist", [])
                if len(blacklist) > 0:
                    print(f"Generating Profanity object for server '{server.name}'")
                    self.guild_profanity_checks[server.id] = Profanity(blacklist)
                    print(f"Profanity object for server '{server.name}' generated")
            await asyncio.sleep(0)
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
                        # Cache these in tmp so that we aren't spamming Github
                        # in case the bot is being constantly restarted
                        with open(f"/tmp/profanities-{lang}", "w") as f:
                            f.write(response.text)
                    await asyncio.sleep(0)
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
    
    def scan_nsfw(
        self,
        url: str=None,
        path: str=None,
    ):
        if url and path:
            raise ValueError("Cannot specify both a URL and a path")
        
        if url:
            download = requests.get(url, headers={
                "User-Agent": USER_AGENT,
            })
            if download.ok:
                rnd_id = str(uuid.uuid4())
                path = f"/tmp/{rnd_id}"
                with open(path, "wb") as f:
                    f.write(download.content)
        
        try:
            raw_result: list = self.nude_detector.detect(path)
        except:
            raw_result = []
        result = {}
        for item in raw_result:
            if result.get(item["class"]) != None:
                # Set it to whichever is higher
                result[item["class"]] = result[item["class"]] + item["score"]
            else:
                result[item["class"]] = item["score"]
        
        image = read_image(path)
        preds = self.nsfw_model([image])
        nsfw_pred = tf.get_static_value(preds[0])[0]
        
        result["NSFW_MODEL"] = nsfw_pred
        
        weights, nudity = weight_filters(result, {
            "FEMALE_GENITALIA_COVERED": 0.25,
            "FACE_FEMALE": 0,
            "BUTTOCKS_EXPOSED": 0.35,
            "FEMALE_BREAST_EXPOSED": 0.85,
            "FEMALE_GENITALIA_EXPOSED": 0.9,
            "MALE_BREAST_EXPOSED": 0.1,
            "ANUS_EXPOSED": 0.35,
            "FEET_EXPOSED": 0.05,
            "BELLY_COVERED": 0,
            "FEET_COVERED": 0,
            "ARMPITS_COVERED": 0,
            "ARMPITS_EXPOSED": 0.15,
            "FACE_MALE": 0,
            "BELLY_EXPOSED": 0.45,
            "MALE_GENITALIA_EXPOSED": 0.9,
            "ANUS_COVERED": 0,
            "FEMALE_BREAST_COVERED": 0.15,
            "BUTTOCKS_COVERED": 0.1,
            "NSFW_MODEL": 0.9,
        }, {
            "FEMALE_GENITALIA_COVERED": 0.25,
            "BELLY_COVERED": 0.25,
            "FEET_COVERED": 0.25,
            "ARMPITS_COVERED": 0.25,
            "ANUS_COVERED": 0.25,
            "FEMALE_BREAST_COVERED": 0.25,
            "BUTTOCKS_COVERED": 0.25,
        })
        
        print(weights)
        print(round(nudity * 100))
        
        os.remove(path)
        
        return nudity
    
    def apply_filters(self, content: str):
        content = strip_md(content)
        content = unidecode(content)

        prediction = filter.predict(content, self.rnn_model)

        toxicity_weights, toxicity = weight_filters(prediction, {
            "obscene": 0.2,
            "insult": 0.2,
            "threat": 0.2,
            "toxic": 0.8,
            "identity_hate": 0.2,
            "severe_toxic": 0.7,
            "neutral": 0,
        }, {
            "neutral": 0.7,
        })
        hatespeech_weights, hatespeech = weight_filters(prediction, {
            "obscene": 0.15,
            "insult": 0.15,
            "threat": 0.15,
            "toxic": 0,
            "identity_hate": 0.5,
            "severe_toxic": 0.3,
            "neutral": 0,
        }, {
            "neutral": 0.5,
        })
        
        return toxicity, hatespeech
    
    async def filter_message(self, message):
        if not getattr(message, "server", False): return
        if not getattr(message, "channel", False): return
        if not getattr(message, "author", False): return
        if message.author.bot: return
        async def run_async():
            context: AutomodContext = await AutomodContext.prepare(message)
            try:
                guild = await db.servers.fetch_or_create_server(message.server)
            except Exception as e:
                return
            else:
                log_channel_id = guild.settings.get("logs_automod")
                log_channel = None
                if log_channel_id:
                    try:
                        log_channel = await self.bot.getch_channel(log_channel_id)
                    except:
                        pass
                if context.can_run("spam_filter"):
                    spam_amt = guild.settings.get("spam_filter")
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
                    # print(f"Scanning '{content}'")
                    if context.can_run("default_profanities"):
                        default_profanities = guild.settings.get("default_profanities", [])
                        if len(default_profanities) > 0:
                            # Try to detect the language(s) in the string and
                            # only filter if the language(s) are in the default
                            # profanities list
                            for result in self.language_detector.detect_multiple_languages_of(content):
                                code = LANG_MAP.get(result.language.name)
                                # print(f"Detected language '{code}'")
                                if code and code in default_profanities:
                                    profanity_check: Profanity = self.default_profanity_checks.get(code)
                                    if profanity_check:
                                        filtered = profanity_check.censor(content)
                                        if filtered != content:
                                            await message.delete()
                                            await self.notify_filter(message, "Profanity Detected")
                                            await self.send_log(log_channel, message, content, "Profanity", {"filtered": filtered})
                                            return
                    if context.can_run("word_blacklist"):
                        profanity: Profanity = self.guild_profanity_checks.get(message.server.id)
                        if profanity:
                            filtered = profanity.censor(content)
                            if filtered != content:
                                await message.delete()
                                await self.notify_filter(message, "Filtered Word Detected")
                                await self.send_log(log_channel, message, content, "Profanity", {"filtered": filtered})
                                return
                    if context.can_run("malicious_urls"):
                        if guild.settings.get("malicious_urls", False):
                            for url in self.malicious_urls.keys():
                                if url in content:
                                    await message.delete()
                                    await self.notify_filter(message, "Malicious URL!")
                                    await self.send_log(log_channel, message, content, "Malicious URL", {"threat": self.malicious_urls[url]})
                                    return
                    if context.can_run("filter_invites"):
                        if guild.settings.get("filter_invites", False):
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
                    if context.can_run("filter_api_keys"):
                        if guild.settings.get("filter_api_keys", False):
                            for regex in API_KEY_REGEXES:
                                match = re.match(regex, content)
                                if match:
                                    await message.delete()
                                    await self.notify_filter(message, "API Key Detected")
                                    await self.send_log(log_channel, message, content, "API Key", {
                                        "redact": [match.group(0)]
                                    })
                                    return
                    if context.can_run("filter_mass_mentions"):
                        if guild.settings.get("filter_mass_mentions", False):
                            mention_count = 0
                            for mention in re.findall("<@([a-zA-Z0-9]{8,10})>|<@&([0-9]*)>"):
                                mention_count += 1
                            if mention_count > 6:
                                await message.delete()
                                await self.notify_filter(message, "Mass Mention Detected")
                                await self.send_log(log_channel, message, content, "Mass Mention")
                                return
                    if self.filters_ready and (guild.settings.get("filter_toxicity", 0) > 0 or guild.settings.get("filter_hatespeech", 0)):
                        if context.can_run("filter_toxicity") or context.can_run("filter_hatespeech"):
                            toxicity, hatespeech = self.apply_filters(content)

                            toxicity_threshold = guild.settings.get("filter_toxicity", 0)
                            if toxicity_threshold > 0 and context.can_run("filter_toxicity"):
                                if (toxicity * 100) >= toxicity_threshold or (toxicity * 100) >= 50:
                                    await self.send_log(log_channel, message, content, "Toxicity", {
                                        "certainty": toxicity,
                                    })
                                if (toxicity * 100) >= toxicity_threshold:
                                    await message.delete()
                                    await self.notify_filter(message, "Toxicity Detected")
                                    return
                            
                            hatespeech_threshold = guild.settings.get("filter_hatespeech", 0)
                            if hatespeech_threshold > 0 and context.can_run("filter_hatespeech"):
                                if (hatespeech * 100) >= hatespeech_threshold or (hatespeech * 100) >= 50:
                                    await self.send_log(log_channel, message, content, "Hatespeech", {
                                        "certainty": hatespeech,
                                    })
                                if (hatespeech * 100) >= hatespeech_threshold:
                                    await message.delete()
                                    await self.notify_filter(message, "Hatespeech Detected")
                                    return
                    if config.LOAD_NSFW and guild.settings.get("premium", "0")[0] == "1" and context.can_run("filter_nsfw") and guild.settings.get("filter_nsfw", 0) > 0:
                        try:
                            for item in _extract_attachments(message._state, content):
                                item: guilded.Attachment
                                if any(f'.{ele}' in item.url for ele in ['jpeg', 'jpg', 'tif', 'tiff', 'gif', 'jif', 'png', 'webp', 'bmp', 'apng']):
                                    nudity = round(self.scan_nsfw(url=item.url) * 100)
                                    if nudity >= 50 or nudity >= guild.settings["filter_nsfw"]:
                                        try:
                                            nsfw_log_channel = await self.bot.getch_channel(guild.settings.get("logs_nsfw"))
                                        except:
                                            nsfw_log_channel = None
                                        await self.send_log(log_channel, message, content, "NSFW", {
                                            "certainty": nudity,
                                        })
                                    if nudity >= guild.settings["filter_nsfw"]:
                                        await message.delete()
                                        await self.notify_filter(message, "NSFW Detected")
                                        return
                        except Exception as e:
                            print(e)
                            import traceback
                            traceback.print_exc()
                                    
                    if len(guild.settings.get("untrusted_block_attachments", [])) > 0:
                        is_trusted = await user_has_permissions(message.author, is_trusted=True)
                        if not is_trusted:
                            block_message = False
                            blocked_type = None
                            for link in re.findall(r'((?:https?://)?[\w\-\.]+(?:/[\w\-_~&=/?\.]+)?)', content):
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
                                    for t in guild.settings.get("untrusted_block_attachments", []):
                                        t: str
                                        if mimeType[0].startswith(t):
                                            block_message = True
                                            blocked_type = t.capitalize()
                                            break
                                else:
                                    head_resp: requests.Response = requests.head(link, headers={
                                        "user-agent": USER_AGENT,
                                    })
                                    if head_resp.ok:
                                        content_type = head_resp.headers.get("content-type")
                                        content_disposition = head_resp.headers.get("content-disposition", "")
                                        dis_mimeType = mimetypes.guess_type(content_disposition)
                                        if "html" in content_type:
                                            page_resp: requests.Response = requests.get(link, headers={
                                                "user-agent": USER_AGENT,
                                            })
                                            if page_resp.ok:
                                                parsed = BeautifulSoup(page_resp.text, features="lxml")
                                                if "image" in guild.settings["untrusted_block_attachments"]:
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
                                                if "video" in guild.settings["untrusted_block_attachments"] and not block_message:
                                                    is_video = False
                                                    for tag in parsed(
                                                        'meta',
                                                        attrs={
                                                            'property': [
                                                                'og:video:url',
                                                                'og:video:secure_url',
                                                                'twitter:image:src',
                                                                'twitter:player'
                                                            ]
                                                        }
                                                    ):
                                                        is_video = True
                                                    for tag in parsed('meta', attrs={'property': ['og:type']}):
                                                        og_type: str = tag['content'].lower().strip()
                                                        if og_type.startswith(('video')):
                                                            is_video = True
                                                    for tag in parsed('meta', attrs={'name': ['keywords']}):
                                                        keywords: str = tag['content'].lower()
                                                        if 'video' in keywords or 'camera phone' in keywords:
                                                            is_video = True
                                                    if is_video:
                                                        block_message = True
                                                        blocked_type = "Video"
                                                if "audio" in guild.settings["untrusted_block_attachments"] and not block_message:
                                                    is_audio = False
                                                    for tag in parsed('meta', attrs={'property': ['og:type']}):
                                                        og_type: str = tag['content'].lower().strip()
                                                        if og_type.startswith(('music')):
                                                            is_audio = True
                                                    if is_audio:
                                                        block_message = True
                                                        blocked_type = "Audio"
                                        else:
                                            for t in guild.settings["untrusted_block_attachments"]:
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
        self.bot.loop.create_task(run_async())

    async def refresh_filter(self, guild_id: str, profanities: list=None):
        if profanities is None:
            try:
                guild = await db.servers.fetch_or_create_server(guild_id)
            except:
                return
            else:
                profanities = guild.settings.get("word_blacklist", [])
        
        if len(profanities) > 0:
            self.guild_profanity_checks[guild_id] = Profanity(profanities)
        else:
            if self.guild_profanity_checks.get(guild_id):
                del self.guild_profanity_checks[guild_id]
                self.guild_profanity_checks[guild_id] = None
    
    @commands.Cog.listener()
    async def on_ready(self):
        if not self.filters_ready:
            await self.__load_guild_profanities()
            await self.__load_profanities()
            await self.__prepare_filters()
    
    @commands.Cog.listener()
    async def on_bot_add(self, event: guilded.BotAddEvent):
        await self.refresh_filter(event.server.id)
    
    @commands.Cog.listener()
    async def on_bot_remove(self, event: guilded.BotRemoveEvent):
        if self.guild_profanity_checks.get(event.server.id):
            del self.guild_profanity_checks[event.server.id]
            self.guild_profanity_checks[event.server.id] = None
        if self.spam_cooldowns.get(event.server.id):
            del self.spam_cooldowns[event.server.id]
            self.spam_cooldowns[event.server.id] = None
    
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

class AutomodContext:
    def __init__(self, server: db.servers.Server, author_perms: UserPermissions, author_roles: list, message: guilded.ChatMessage):
        self.server = server
        self.author_perms = author_perms
        self.author_roles = author_roles
        self.message = message
    
    @classmethod
    async def prepare(cls, message: guilded.ChatMessage):
        try:
            guild = await db.servers.fetch_or_create_server(message.server)
            user = await guild.fetch_or_create_member(message.author)
        except:
            raise RuntimeError("Failed to retrieve guild data")
        else:
            return AutomodContext(guild, user.perms, user.roles, message)
    
    def can_run(self, setting: str):
        restrictions = self.server.settings.get(f"{setting}_restrictions", {})
        
        allowed_users = restrictions.get("allow_users", [])
        allowed_roles = restrictions.get("allow_roles", [])
        allowed_channels = restrictions.get("allow_channels", [])
        
        blacklisted_users = restrictions.get("blacklist_users", [])
        blacklisted_roles = restrictions.get("blacklist_roles", [])
        blacklisted_channels = restrictions.get("blacklist_channels", [])
        
        allowed = not self.author_perms.bypass_filter
        
        if self.message.author.id in allowed_users:
            allowed = True
        if self.message.channel.id in allowed_channels:
            allowed = True
        if any(role.id in allowed_roles for role in self.message.author.roles):
            allowed = True
        
        # Blacklist will take priority over the whitelist
        if self.message.author.id in blacklisted_users:
            allowed = False
        if self.message.channel.id in blacklisted_channels:
            allowed = False
        if any(role.id in blacklisted_roles for role in self.message.author.roles):
            allowed = False
        
        return allowed

def setup(bot: commands.Bot):
    bot.add_cog(Automod(bot))