from youtube import util
from .get_app_version import app_version
import flask
from flask import request
import jinja2
import settings
import traceback
import re
from sys import exc_info
yt_app = flask.Flask(__name__)
yt_app.config['TEMPLATES_AUTO_RELOAD'] = True
yt_app.url_map.strict_slashes = False
# yt_app.jinja_env.trim_blocks = True
# yt_app.jinja_env.lstrip_blocks = True

# https://stackoverflow.com/questions/39858191/do-statement-not-working-in-jinja
yt_app.jinja_env.add_extension('jinja2.ext.do') # why

yt_app.add_url_rule('/settings', 'settings_page', settings.settings_page, methods=['POST', 'GET'])


@yt_app.route('/')
def homepage():
    return flask.render_template('home.html', title="YouTube Local")


@yt_app.route('/licenses')
def licensepage():
    return flask.render_template(
        'licenses.html',
        title="Licenses - YouTube Local"
    )


theme_names = {
    0: 'light_theme',
    1: 'gray_theme',
    2: 'dark_theme',
}


@yt_app.context_processor
def inject_theme_preference():
    return {
        'theme_path': '/youtube.com/static/' + theme_names[settings.theme] + '.css',
        'settings': settings,
        # Detect version
        'current_version': app_version()['version'],
        'current_branch': app_version()['branch'],
        'current_commit': app_version()['commit'],
    }


@yt_app.template_filter('commatize')
def commatize(num):
    if num is None:
        return ''
    if isinstance(num, str):
        try:
            num = int(num)
        except ValueError:
            return num
    return '{:,}'.format(num)


def timestamp_replacement(match):
    time_seconds = 0
    for part in match.group(0).split(':'):
        time_seconds = 60*time_seconds + int(part)
    return (
        """
          <a href="#" id="timestamp%s">%s</a>
          <script>
           // @license magnet:?xt=urn:btih:0b31508aeb0634b347b8270c7bee4d411b5d4109&dn=agpl-3.0.txt AGPL-v3-or-Later
           (function main() {
             'use strict';
             const player = document.getElementById('js-video-player');
             const a = document.getElementById('timestamp%s');
             a.addEventListener('click', function(event) {
               player.currentTime = %s
             });
           }());
           // @license-end
          </script>
        """ % (
            str(time_seconds),
            match.group(0),
            str(time_seconds),
            str(time_seconds)
        )
    )


TIMESTAMP_RE = re.compile(r'\b(\d?\d:)?\d?\d:\d\d\b')


@yt_app.template_filter('timestamps')
def timestamps(text):
    return TIMESTAMP_RE.sub(timestamp_replacement, text)


@yt_app.errorhandler(500)
def error_page(e):
    slim = request.args.get('slim', False) # whether it was an ajax request
    if (exc_info()[0] == util.FetchError
        and exc_info()[1].code == '429'
        and settings.route_tor
    ):
        error_message = ('Error: YouTube blocked the request because the Tor'
            ' exit node is overutilized. Try getting a new exit node by'
            ' using the New Identity button in the Tor Browser.')
        if exc_info()[1].error_message:
            error_message += '\n\n' + exc_info()[1].error_message
        if exc_info()[1].ip:
            error_message += '\n\nExit node IP address: ' + exc_info()[1].ip
        return flask.render_template('error.html', error_message=error_message, slim=slim), 502
    elif exc_info()[0] == util.FetchError and exc_info()[1].error_message:
        return (flask.render_template(
                    'error.html',
                    error_message=exc_info()[1].error_message,
                    slim=slim
                ), 502)
    elif (exc_info()[0] == util.FetchError
        and exc_info()[1].code == '404'
    ):
        error_message = ('Error: The page you are looking for isn\'t here.')
        return flask.render_template('error.html',
                                     error_code=exc_info()[1].code,
                                     error_message=error_message,
                                     slim=slim), 404
    return flask.render_template('error.html', traceback=traceback.format_exc(),
                                 error_code=exc_info()[1].code,
                                 slim=slim), 500
    # return flask.render_template('error.html', traceback=traceback.format_exc(), slim=slim), 500


font_choices = {
    0: 'initial',
    1: '"liberation serif", "times new roman", calibri, carlito, serif',
    2: 'arial, "liberation sans", sans-serif',
    3: 'verdana, sans-serif',
    4: 'tahoma, sans-serif',
}


@yt_app.route('/shared.css')
def get_css():
    return flask.Response(
        flask.render_template(
            'shared.css',
            font_family=font_choices[settings.font]
        ),
        mimetype='text/css',
    )


# This is okay because the flask urlize function puts the href as the first
# property
YOUTUBE_LINK_RE = re.compile(r'<a href="(' + util.YOUTUBE_URL_RE_STR + ')"')
old_urlize = jinja2.filters.urlize


def prefix_urlize(*args, **kwargs):
    result = old_urlize(*args, **kwargs)
    return YOUTUBE_LINK_RE.sub(r'<a href="/\1"', result)


jinja2.filters.urlize = prefix_urlize
