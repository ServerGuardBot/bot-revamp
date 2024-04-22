from modules.automod import LDNOOBW_LANGS
from core.setting_handlers import *
from core import defaults, limits

modules = list_handler(defaults.modules, lowercase=True)
prefix = string_handler(lowercase=True, max_length=10)
nickname = string_handler(max_length=40)
timezone = timezone_handler
language = language_handler
permissions = permission_handler

unverified_role = role_handler
verified_role = role_handler
muted_role = role_handler

filter_mass_mentions = bool_handler
filter_mass_mentions_restrictions = automod_restriction_handler

filter_api_keys = bool_handler
filter_api_keys_restrictions = automod_restriction_handler

malicious_urls = bool_handler
malicious_urls_restrictions = automod_restriction_handler

filter_invites = bool_handler
filter_invites_restrictions = automod_restriction_handler

filter_nsfw = is_premium_server(number_handler(min=0, max=100))
filter_nsfw_restrictions = automod_restriction_handler

filter_hatespeech = number_handler(min=0, max=100)
filter_hatespeech_restrictions = automod_restriction_handler

filter_toxicity = number_handler(min=0, max=100)
filter_toxicity_restrictions = automod_restriction_handler

spam_filter = number_handler(min=0)
spam_filter_restrictions = automod_restriction_handler

untrusted_block_attachments = list_handler(
    ["image", "audio", "video", "application", "font"]
)
default_profanities = list_handler(LDNOOBW_LANGS)
default_profanities_restrictions = automod_restriction_handler

word_blacklist = blacklist_handler
word_blacklist_restrictions = automod_restriction_handler

silence_commands = bool_handler
log_commands = bool_handler
log_roles = bool_handler

logs_nsfw = is_premium_server(channel_handler("text"))
logs_verification = channel_handler("text")
logs_management = channel_handler("text")
logs_traffic = channel_handler("text")
logs_message = channel_handler("text")
logs_action = channel_handler("text")
logs_user = channel_handler("text")
logs_automod = channel_handler("text")

verification_channel = channel_handler("text")
admin_contact = contact_handler
raid_guard = bool_handler
block_tor = bool_handler
check_ips = bool_handler

re_nsfw = is_premium_server(number_handler(min=0, max=100))
re_hatespeech = number_handler(min=0, max=100)
re_toxicity = number_handler(min=0, max=100)
re_blacklist = blacklist_handler

remove_old_level_roles = bool_handler
announce_level_up = bool_handler
xp_roles = xp_role_handler

send_welcome = bool_handler
welcome_message = string_handler(
    max_length=limits.welcomer_message_length,
)
welcome_channel = channel_handler("text")
welcome_image = url_handler
welcome_image_cycle = welcomer_cycle

send_goodbye = bool_handler
goodbye_message = string_handler(
    max_length=limits.welcomer_message_length,
)
goodbye_channel = channel_handler("text")
goodbye_image = url_handler
goodbye_image_cycle = welcomer_cycle

rss_feeds = uses_custom_handler

giveaway_ping_role = role_handler
giveaway_channel = channel_handler("text")