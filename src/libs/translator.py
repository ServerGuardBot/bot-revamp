from guilded.ext import commands
from os import path

import database as db
import requests
import config
import i18n

BASE = config.WEBLATE_ROOT + "/api"
PROJECT = config.WEBLATE_PROJECT
HEADERS = {
    "Authorization": f"Token {config.WEBLATE_TOKEN}",
    "Accept": "application/json"
}

WEBLATE_ONLINE = False

languages = []

i18n.load_path = [path.join(path.dirname(__file__), "..", "localization")]

def refresh_languages():
    global languages
    global WEBLATE_ONLINE
    if not WEBLATE_ONLINE:
        return
    print("Refreshing languages...")
    req = requests.get(f"{BASE}/languages/", headers=HEADERS)
    if req.ok:
        json = req.json()["results"]
        for item in json:
            if not item["code"] in languages:
                languages.append(item["code"])
                print(f"Added language {item['code']}")
        
        for item in languages:
            if not any([l["code"] == item for l in json]):
                languages.remove(item)
                print(f"Removed language {item}")
        
        components_req = requests.get(f"{BASE}/components/", headers=HEADERS)
        if components_req.ok:
            components = []
            for item in components_req.json()["results"]:
                if item["project"]["slug"] == PROJECT:
                    components.append(item["slug"])
            
            for lang in languages:
                for component in components:
                    file_req = requests.get(f"{BASE}/translations/{PROJECT}/{component}/{lang}/file/", headers=HEADERS)
                    if file_req.ok:
                        file_path = path.join(path.dirname(__file__), "..", "localization", f"{component}.{lang}.json")
                        with open(file_path, "rw") as file:
                            if file.read() != file_req.text:
                                file.write(file_req.text)
                                print(f"Saved {component}.{lang}")

class TranslationContext:
    def __init__(self, locale):
        self.locale = locale

    def t(self, key):
        return i18n.t(key, locale=self.locale)

class Translator:
    async def __init__(
        self,
        server_id: str,
        user_id: str,
    ):
        user_locale = None
        guild_locale = None
        if user_id:
            try:
                user = await db.users.fetch_user(user_id)
            except Exception as e:
                print(e)
            else:
                user_locale = user.language
        if server_id:
            try:
                guild = await db.servers.fetch_server(server_id)
            except Exception as e:
                print(e)
            else:
                guild_locale = guild.settings.get("language", "en")
        
        if user_locale:
            self.user = TranslationContext(user_locale)
        else:
            if guild_locale:
                self.user = TranslationContext(guild_locale)
            else:
                self.user = TranslationContext("en")
        
        if guild_locale and not user_locale:
            self.guild = TranslationContext(guild_locale)
        else:
            if user_locale:
                self.guild = TranslationContext(user_locale)
            else:
                self.guild = TranslationContext("en")
    
    @classmethod
    async def from_context(cls, ctx: commands.Context):
        return await cls(
            server_id=ctx.server.id,
            user_id=ctx.author.id
        )

if __name__ == "__main__":
    req = requests.get(f"{BASE}/")
    if req.ok:
        try:
            js = req.json()
        except:
            WEBLATE_ONLINE = False
        else:
            # Validate that the response is that of a valid Weblate server
            # if so, set the global variable to indicate that Weblate is online.
            # useful in development where we don't always need access the the
            # server.
            if js.get("languages") and js.get("components") and js.get("translations"):
                WEBLATE_ONLINE = True