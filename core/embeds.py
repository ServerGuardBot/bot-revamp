from datetime import datetime
from core.images import IMAGE_BOT_LOGO, IMAGE_DENIED
from guilded import Embed, Colour, Member
from guilded.embed import EmptyEmbed

import config

def EMBED_STANDARD(title: str, description: str, colour: Colour = Colour.gilded(), timestamp: datetime = EmptyEmbed, url: str = EmptyEmbed):
    from base import BOT_VERSION
    return Embed(
        title=title,
        description=description,
        colour=colour,
        timestamp=timestamp or datetime.now(),
        url = url
    ).set_footer(
        text=f"v{BOT_VERSION} {str.capitalize(config.DATABASE_DB)}",
        icon_url=IMAGE_BOT_LOGO,
    )

def EMBED_DENIED(title: str, description: str, colour: Colour = Colour.red(), timestamp: datetime = EmptyEmbed, url: str = EmptyEmbed):
    return EMBED_STANDARD(title, description, colour, timestamp, url).set_thumbnail(url=IMAGE_DENIED)

def EMBED_SUCCESS(title: str, description: str, colour: Colour = Colour.green(), timestamp: datetime = EmptyEmbed, url: str = EmptyEmbed):
    return EMBED_STANDARD(title, description, colour, timestamp, url)

# TODO: i18n support
def EMBED_FILTERED(member: Member, reason: str):
    return EMBED_STANDARD(
        title="Message filtered",
        description=f"Hey there, {member.mention}, your message was removed by one of this server's filters for \"{reason}\"\n\nPlease do not do this again or moderation actions may be taken against you.",
        colour=Colour.orange()
    )