default_settings = '''route_tor = False
port_number = 80
allow_foreign_addresses = False

# 0 - off by default
# 1 - only manually created subtitles on by default
# 2 - enable even if automatically generated is all that's available
subtitles_mode = 0

# ISO 639 language code: https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes
subtitles_language = "en"

enable_related_videos = True
enable_comments = True
enable_comment_avatars = True

# 0 to sort by top
# 1 to sort by newest
default_comment_sorting = 0

# developer use to debug 403s
gather_googlevideo_domains = False
'''
exec(default_settings)
try:
    with open('settings.txt', 'r', encoding='utf-8') as file:
        exec(file.read())
except FileNotFoundError:
    with open('settings.txt', 'a', encoding='utf-8') as file:
        file.write(default_settings)