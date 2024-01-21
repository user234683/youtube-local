from youtube import util
import ast
import re
import os
import collections

import flask
from flask import request

SETTINGS_INFO = collections.OrderedDict([
    ('route_tor', {
        'type': int,
        'default': 0,
        'label': 'Route Tor',
        'comment': '''0 - Off
1 - On, except video
2 - On, including video (see warnings)''',
        'options': [
            (0, 'Off'),
            (1, 'On, except video'),
            (2, 'On, including video (see warnings)'),
        ],
        'category': 'network',
    }),

    ('tor_port', {
        'type': int,
        'default': 9150,
        'comment': '',
        'category': 'network',
    }),

    ('tor_control_port', {
        'type': int,
        'default': 9151,
        'comment': '',
        'category': 'network',
    }),

    ('port_number', {
        'type': int,
        'default': 8080,
        'comment': '',
        'category': 'network',
    }),

    ('allow_foreign_addresses', {
        'type': bool,
        'default': False,
        'comment': '''This will allow others to connect to your Youtube Local instance as a website.
For security reasons, enabling this is not recommended.''',
        'hidden': True,
        'category': 'network',
    }),

    ('allow_foreign_post_requests', {
        'type': bool,
        'default': False,
        'comment': '''Enables requests from foreign addresses to make post requests.
For security reasons, enabling this is not recommended.''',
        'hidden': True,
        'category': 'network',
    }),

    ('subtitles_mode', {
        'type': int,
        'default': 0,
        'comment': '''0 - off by default
1 - only manually created subtitles on by default
2 - enable even if automatically generated is all that's available''',
        'label': 'Default subtitles mode',
        'options': [
            (0, 'Off'),
            (1, 'Manually created only'),
            (2, 'Automatic if manual unavailable'),
        ],
        'category': 'playback',
    }),

    ('subtitles_language', {
        'type': str,
        'default': 'en',
        'comment': '''ISO 639 language code: https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes''',
        'category': 'playback',
    }),

    ('related_videos_mode', {
        'type': int,
        'default': 1,
        'comment': '''0 - Related videos disabled
1 - Related videos always shown
2 - Related videos hidden; shown by clicking a button''',
        'options': [
            (0, 'Disabled'),
            (1, 'Always shown'),
            (2, 'Shown by clicking button'),
        ],
        'category': 'interface',
    }),

    ('comments_mode', {
        'type': int,
        'default': 1,
        'comment': '''0 - Video comments disabled
1 - Video comments always shown
2 - Video comments hidden; shown by clicking a button''',
        'options': [
            (0, 'Disabled'),
            (1, 'Always shown'),
            (2, 'Shown by clicking button'),
        ],
        'category': 'interface',
    }),

    ('enable_comment_avatars', {
        'type': bool,
        'default': True,
        'comment': '',
        'category': 'interface',
    }),

    ('default_comment_sorting', {
        'type': int,
        'default': 0,
        'comment': '''0 to sort by top
1 to sort by newest''',
        'options': [
            (0, 'Top'),
            (1, 'Newest'),
        ],
    }),

    ('theater_mode', {
        'type': bool,
        'default': True,
        'comment': '',
        'category': 'interface',
    }),

    ('default_resolution', {
        'type': int,
        'default': 720,
        'comment': '',
        'options': [
            (144, '144p'),
            (240, '240p'),
            (360, '360p'),
            (480, '480p'),
            (720, '720p'),
            (1080, '1080p'),
            (1440, '1440p'),
            (2160, '2160p'),
        ],
        'category': 'playback',
    }),

    ('autoplay_videos', {
        'type': bool,
        'default': False,
        'comment': '',
        'category': 'playback',
    }),

    ('codec_rank_h264', {
        'type': int,
        'default': 1,
        'label': 'H.264 Codec Ranking',
        'comment': '',
        'options': [(1, '#1'), (2, '#2'), (3, '#3')],
        'category': 'playback',
        'description': (
            'Which video codecs to prefer. Codecs given the same '
            'ranking will use smaller file size as a tiebreaker.'
        )
    }),

    ('codec_rank_vp', {
        'type': int,
        'default': 2,
        'label': 'VP8/VP9 Codec Ranking',
        'comment': '',
        'options': [(1, '#1'), (2, '#2'), (3, '#3')],
        'category': 'playback',
    }),

    ('codec_rank_av1', {
        'type': int,
        'default': 3,
        'label': 'AV1 Codec Ranking',
        'comment': '',
        'options': [(1, '#1'), (2, '#2'), (3, '#3')],
        'category': 'playback',
    }),

    ('prefer_uni_sources', {
        'label': 'Use integrated sources',
        'type': int,
        'default': 1,
        'comment': '',
        'options': [
            (0, 'Prefer not'),
            (1, 'Prefer'),
            (2, 'Always'),
        ],
        'category': 'playback',
        'description': 'If set to Prefer or Always and the default resolution is set to 360p or 720p, uses the unified (integrated) video files which contain audio and video, with buffering managed by the browser. If set to prefer not, uses the separate audio and video files through custom buffer management in av-merge via MediaSource unless they are unavailable.',
    }),

    ('use_video_hotkeys', {
        'label': 'Enable video hotkeys',
        'type': bool,
        'default': True,
        'comment': '',
        'category': 'interface',
    }),

    ('video_player', {
        'type': int,
        'default': 1,
        'comment': '',
        'options': [
            (0, 'Browser Default'),
            (1, 'Plyr'),
        ],
        'category': 'interface',
    }),

    ('proxy_images', {
        'label': 'Route images',
        'type': bool,
        'default': True,
        'comment': '',
        'category': 'network',
    }),

    ('use_comments_js', {
        'label': 'Enable comments.js',
        'type': bool,
        'default': True,
        'comment': '',
        'category': 'interface',
    }),

    ('use_sponsorblock_js', {
        'label': 'Enable SponsorBlock',
        'type': bool,
        'default': False,
        'comment': '',
        'category': 'playback',
    }),

    ('theme', {
        'type': int,
        'default': 0,
        'comment': '',
        'options': [
            (0, 'Light'),
            (1, 'Gray'),
            (2, 'Dark'),
        ],
        'category': 'interface',
    }),

    ('font', {
        'type': int,
        'default': 1,
        'comment': '',
        'options': [
            (0, 'Browser default'),
            (1, 'Arial'),
            (2, 'Liberation Serif'),
            (3, 'Verdana'),
            (4, 'Tahoma'),
        ],
        'category': 'interface',
    }),

    ('embed_page_mode', {
        'type': bool,
        'label': 'Enable embed page',
        'default': True,
        'comment': '',
        'category': 'interface',
    }),

    ('autocheck_subscriptions', {
        'type': bool,
        'default': 0,
        'comment': '',
    }),
    ('include_shorts_in_subscriptions', {
        'type': bool,
        'default': 0,
        'comment': '',
    }),
    ('include_shorts_in_channel', {
        'type': bool,
        'default': 1,
        'comment': '',
    }),

    ('gather_googlevideo_domains', {
        'type': bool,
        'default': False,
        'comment': '''Developer use to debug 403s''',
        'hidden': True,
    }),

    ('debugging_save_responses', {
        'type': bool,
        'default': False,
        'comment': '''Save all responses from youtube for debugging''',
        'hidden': True,
    }),

    ('settings_version', {
        'type': int,
        'default': 5,
        'comment': '''Do not change, remove, or comment out this value, or else your settings may be lost or corrupted''',
        'hidden': True,
    }),
])

program_directory = os.path.dirname(os.path.realpath(__file__))
acceptable_targets = SETTINGS_INFO.keys() | {
    'enable_comments', 'enable_related_videos', 'preferred_video_codec'
}


def comment_string(comment):
    result = ''
    for line in comment.splitlines():
        result += '# ' + line + '\n'
    return result

def save_settings(settings_dict):
    with open(settings_file_path, 'w', encoding='utf-8') as file:
        for setting_name, setting_info in SETTINGS_INFO.items():
            file.write(comment_string(setting_info['comment']) + setting_name + ' = ' + repr(settings_dict[setting_name]) + '\n\n')

def add_missing_settings(settings_dict):
    result = default_settings()
    result.update(settings_dict)
    return result

def default_settings():
    return {key: setting_info['default'] for key, setting_info in SETTINGS_INFO.items()}

def upgrade_to_2(settings_dict):
    '''Upgrade to settings version 2'''
    new_settings = settings_dict.copy()
    if 'enable_comments' in settings_dict:
        new_settings['comments_mode'] = int(settings_dict['enable_comments'])
        del new_settings['enable_comments']
    if 'enable_related_videos' in settings_dict:
        new_settings['related_videos_mode'] = int(settings_dict['enable_related_videos'])
        del new_settings['enable_related_videos']
    new_settings['settings_version'] = 2
    return new_settings

def upgrade_to_3(settings_dict):
    new_settings = settings_dict.copy()
    if 'route_tor' in settings_dict:
        new_settings['route_tor'] = int(settings_dict['route_tor'])
    new_settings['settings_version'] = 3
    return new_settings
def upgrade_to_4(settings_dict):
    new_settings = settings_dict.copy()
    if 'preferred_video_codec' in settings_dict:
        pref = settings_dict['preferred_video_codec']
        if pref == 0:
            new_settings['codec_rank_h264'] = 1
            new_settings['codec_rank_vp'] = 2
            new_settings['codec_rank_av1'] = 3
        else:
            new_settings['codec_rank_h264'] = 3
            new_settings['codec_rank_vp'] = 2
            new_settings['codec_rank_av1'] = 1
        del new_settings['preferred_video_codec']
    new_settings['settings_version'] = 4
    return new_settings

def upgrade_to_5(settings_dict):
    new_settings = settings_dict.copy()
    if 'prefer_uni_sources' in settings_dict:
        new_settings['prefer_uni_sources'] = int(settings_dict['prefer_uni_sources'])
    new_settings['settings_version'] = 5
    return new_settings

upgrade_functions = {
    1: upgrade_to_2,
    2: upgrade_to_3,
    3: upgrade_to_4,
    4: upgrade_to_5,
}

def log_ignored_line(line_number, message):
    print("WARNING: Ignoring settings.txt line " + str(node.lineno) + " (" + message + ")")




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

settings_file_path = os.path.join(settings_dir, 'settings.txt')

try:
    with open(settings_file_path, 'r', encoding='utf-8') as file:
        settings_text = file.read()
except FileNotFoundError:
    current_settings_dict = default_settings()
    save_settings(current_settings_dict)
else:
    if re.fullmatch(r'\s*', settings_text):     # blank file
        current_settings_dict = default_settings()
        save_settings(current_settings_dict)
    else:
        # parse settings in a safe way, without exec
        current_settings_dict = {}
        attributes = {
            ast.Constant: 'value',
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

            if target.id not in acceptable_targets:
                log_ignored_line(node.lineno,  target.id + " is not a valid setting")
                continue

            if type(node.value) not in attributes:
                log_ignored_line(node.lineno, "only literals allowed for values")
                continue

            current_settings_dict[target.id] = node.value.__getattribute__(attributes[type(node.value)])

        # upgrades
        latest_version = SETTINGS_INFO['settings_version']['default']
        while current_settings_dict.get('settings_version',1) < latest_version:
            current_version = current_settings_dict.get('settings_version', 1)
            print('Upgrading settings.txt to version', current_version+1)
            upgrade_func = upgrade_functions[current_version]
            # Must add missing settings here rather than below because
            # save_settings needs all settings to be present
            current_settings_dict = add_missing_settings(
                upgrade_func(current_settings_dict))
            save_settings(current_settings_dict)

        # some settings not in the file, add those missing settings to the file
        if not current_settings_dict.keys() >= SETTINGS_INFO.keys():
            print('Adding missing settings to settings.txt')
            current_settings_dict = add_missing_settings(current_settings_dict)
            save_settings(current_settings_dict)

globals().update(current_settings_dict)



if route_tor:
    print("Tor routing is ON")
else:
    print("Tor routing is OFF - your Youtube activity is NOT anonymous")




hooks = {}
def add_setting_changed_hook(setting, func):
    '''Called right after new settings take effect'''
    if setting in hooks:
        hooks[setting].append(func)
    else:
        hooks[setting] = [func]


def set_img_prefix(old_value=None, value=None):
    global img_prefix
    if value is None:
        value = proxy_images
    if value:
        img_prefix = '/'
    else:
        img_prefix = ''
set_img_prefix()
add_setting_changed_hook('proxy_images', set_img_prefix)


categories = ['network', 'interface', 'playback', 'other']
def settings_page():
    if request.method == 'GET':
        settings_by_category = {categ: [] for categ in categories}
        for setting_name, setting_info in SETTINGS_INFO.items():
            categ = setting_info.get('category', 'other')
            settings_by_category[categ].append(
                (setting_name, setting_info, current_settings_dict[setting_name])
            )
        return flask.render_template('settings.html',
            categories = categories,
            settings_by_category = settings_by_category,
        )
    elif request.method == 'POST':
        for key, value in request.values.items():
            if key in SETTINGS_INFO:
                if SETTINGS_INFO[key]['type'] is bool and value == 'on':
                    current_settings_dict[key] = True
                else:
                    current_settings_dict[key] = SETTINGS_INFO[key]['type'](value)
            else:
                flask.abort(400)

        # need this bullshit because browsers don't send anything when an input is unchecked
        expected_inputs = {setting_name for setting_name, setting_info in SETTINGS_INFO.items() if not SETTINGS_INFO[setting_name].get('hidden', False)}
        missing_inputs = expected_inputs - set(request.values.keys())
        for setting_name in missing_inputs:
            assert SETTINGS_INFO[setting_name]['type'] is bool, missing_inputs
            current_settings_dict[setting_name] = False

        # find settings that have changed to prepare setting hook calls
        to_call = []
        for setting_name, value in current_settings_dict.items():
            old_value = globals()[setting_name]
            if value != old_value and setting_name in hooks:
                for func in hooks[setting_name]:
                    to_call.append((func, old_value, value))

        globals().update(current_settings_dict)
        save_settings(current_settings_dict)

        # call setting hooks
        for func, old_value, value in to_call:
            func(old_value, value)

        return flask.redirect(util.URL_ORIGIN + '/settings', 303)
    else:
        flask.abort(400)
