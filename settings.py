import ast
import re
import os

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
allowed_targets = set(("route_tor", "port_number", "allow_foreign_addresses", "subtitles_mode", "subtitles_language", "enable_related_videos", "enable_comments", "enable_comment_avatars", "default_comment_sorting", "gather_googlevideo_domains"))

def log_ignored_line(line_number, message):
    print("settings.txt: Ignoring line " + str(node.lineno) + " (" + message + ")")


if os.path.isfile("settings.txt"):
    print("Running in portable mode")
    settings_dir = os.path.normpath('./')
    data_dir = os.path.normpath('./data')
else:
    print("Running in non-portable mode")
    settings_dir = os.path.expanduser(os.path.normpath("~/.youtube-local"))
    data_dir = os.path.expanduser(os.path.normpath("~/.youtube-local/data"))
    if not os.path.exists(settings_dir):
        os.makedirs(settings_dir)



try:
    with open(os.path.join(settings_dir, 'settings.txt'), 'r', encoding='utf-8') as file:
        settings_text = file.read()
except FileNotFoundError:
    with open(os.path.join(settings_dir, 'settings.txt'), 'a', encoding='utf-8') as file:
        file.write(default_settings)
else:
    if re.fullmatch(r'\s*', settings_text):     # blank file
        with open(os.path.join(settings_dir, 'settings.txt'), 'a', encoding='utf-8') as file:
            file.write(default_settings)
    else:
        attributes = {
            ast.NameConstant: 'value',
            ast.Num: 'n',
            ast.Str: 's',
        }
        module_node = ast.parse(settings_text)
        for node in module_node.body:
            if type(node) != ast.Assign:
                log_ignored_line(node.lineno, "only assignments are allowed")
                continue
            
            if len(node.targets) > 1:
                log_ignored_line(node.lineno, "only simple single-variable assignments allowed")
                continue

            target = node.targets[0]
            if type(target) != ast.Name:
                log_ignored_line(node.lineno, "only simple single-variable assignments allowed")
                continue
            
            if target.id not in allowed_targets:
                log_ignored_line(node.lineno, "target is not a valid setting")
                continue
            
            if type(node.value) not in (ast.NameConstant, ast.Num, ast.Str):
                log_ignored_line(node.lineno, "only literals allowed for values")
                continue

            locals()[target.id] = node.value.__getattribute__(attributes[type(node.value)])
        