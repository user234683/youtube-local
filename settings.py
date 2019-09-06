from youtube import util
import ast
import re
import os
import collections

import flask
from flask import request

settings_info = collections.OrderedDict([
    ('route_tor', {
        'type': bool,
        'default': False,
        'label': 'Route Tor',
        'comment': '',
    }),

    ('port_number', {
        'type': int,
        'default': 8080,
        'comment': '',
    }),

    ('allow_foreign_addresses', {
        'type': bool,
        'default': False,
        'comment': '''This will allow others to connect to your Youtube Local instance as a website.
For security reasons, enabling this is not recommended.''',
        'hidden': True,
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
    }),

    ('subtitles_language', {
        'type': str,
        'default': 'en',
        'comment': '''ISO 639 language code: https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes''',
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
    }),

    ('enable_comment_avatars', {
        'type': bool,
        'default': True,
        'comment': '',
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
    }),

    ('default_resolution', {
        'type': int,
        'default': 720,
        'comment': '',
        'options': [
            (360, '360p'),
            (720, '720p'),
        ],
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
        'default': 2,
        'comment': '''Do not change, remove, or comment out this value, or else your settings may be lost or corrupted''',
        'hidden': True,
    }),
])

acceptable_targets = settings_info.keys() | {'enable_comments', 'enable_related_videos'}


def comment_string(comment):
    result = ''
    for line in comment.splitlines():
        result += '# ' + line + '\n'
    return result

def save_settings(settings):
    with open(settings_file_path, 'w', encoding='utf-8') as file:
        for setting_name, default_setting_dict in settings_info.items():
            file.write(comment_string(default_setting_dict['comment']) + setting_name + ' = ' + repr(settings[setting_name]) + '\n\n')


def create_missing_settings_string(current_settings):
    result = ''
    for setting_name, setting_dict in settings_info.items():
        if setting_name not in current_settings:
            result += comment_string(setting_dict['comment']) + setting_name + ' = ' + repr(setting_dict['default']) + '\n\n'
    return result

def create_default_settings_string():
    return settings_to_string({})

def add_missing_settings(settings):
    result = default_settings()
    result.update(settings)
    return result

def default_settings():
    return {key: setting_info['default'] for key, setting_info in settings_info.items()}

def settings_to_string(settings):
    '''Given a dictionary with the setting names/setting values for the keys/values, outputs a settings file string.
       Fills in missing values from the defaults.'''
    result = ''
    for setting_name, default_setting_dict in settings_info.items():
        if setting_name in settings:
            value = settings[setting_name]
        else:
            value = default_setting_dict['default']
        result += comment_string(default_setting_dict['comment']) + setting_name + ' = ' + repr(value) + '\n\n'
    return result


def upgrade_to_2(current_settings):
    '''Upgrade to settings version 2'''
    new_settings = current_settings.copy()
    if 'enable_comments' in current_settings:
        new_settings['comments_mode'] = int(current_settings['enable_comments'])
        del new_settings['enable_comments']
    if 'enable_related_videos' in current_settings:
        new_settings['related_videos_mode'] = int(current_settings['enable_related_videos'])
        del new_settings['enable_related_videos']
    return new_settings

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
    settings = default_settings()
    save_settings(settings)
else:
    if re.fullmatch(r'\s*', settings_text):     # blank file
        settings = default_settings()
        save_settings(settings)
    else:
        # parse settings in a safe way, without exec
        settings = {}
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
            
            if target.id not in acceptable_targets:
                log_ignored_line(node.lineno,  target.id + " is not a valid setting")
                continue
            
            if type(node.value) not in (ast.NameConstant, ast.Num, ast.Str):
                log_ignored_line(node.lineno, "only literals allowed for values")
                continue

            settings[target.id] = node.value.__getattribute__(attributes[type(node.value)])


        if 'settings_version' not in settings:
            print('Upgrading settings.txt')
            settings = add_missing_settings(upgrade_to_2(settings))
            save_settings(settings)

        # some settings not in the file, add those missing settings to the file
        elif not settings.keys() >= settings_info.keys():
            print('Adding missing settings to settings.txt')
            settings = add_missing_settings(settings)
            save_settings(settings)

locals().update(settings)




if route_tor:
    print("Tor routing is ON")
else:
    print("Tor routing is OFF - your Youtube activity is NOT anonymous")


def settings_page():
    if request.method == 'GET':
        return flask.render_template('settings.html',
            settings = [(setting_name, setting_info, settings[setting_name]) for setting_name, setting_info in settings_info.items()]
        )
    elif request.method == 'POST':
        for key, value in request.values.items():
            if key in settings_info:
                if settings_info[key]['type'] is bool and value == 'on':
                    settings[key] = True
                else:
                    settings[key] = settings_info[key]['type'](value)
            else:
                flask.abort(400)

        # need this bullshit because browsers don't send anything when an input is unchecked
        expected_inputs = {setting_name for setting_name, setting_info in settings_info.items() if not settings_info[setting_name].get('hidden', False)}
        missing_inputs = expected_inputs - set(request.values.keys())
        for setting_name in missing_inputs:
            assert settings_info[setting_name]['type'] is bool, missing_inputs
            settings[setting_name] = False

        globals().update(settings)
        save_settings(settings)
        return flask.redirect(util.URL_ORIGIN + '/settings', 303)
    else:
        flask.abort(400)









