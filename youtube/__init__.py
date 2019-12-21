import flask
import settings
import traceback
yt_app = flask.Flask(__name__)
yt_app.url_map.strict_slashes = False


yt_app.add_url_rule('/settings', 'settings_page', settings.settings_page, methods=['POST', 'GET'])

@yt_app.route('/')
def homepage():
    return flask.render_template('home.html', title="Youtube local")


theme_names = {
    0: 'light_theme',
    1: 'gray_theme',
    2: 'dark_theme',
}

@yt_app.context_processor
def inject_theme_preference():
    return {
        'theme_path': '/youtube.com/static/' + theme_names[settings.theme] + '.css',
    }

@yt_app.template_filter('commatize')
def commatize(num):
    if num is None:
        return ''
    if isinstance(num, str):
        num = int(num)
    return '{:,}'.format(num)

@yt_app.errorhandler(500)
def error_page(e):
    return flask.render_template('error.html', traceback=traceback.format_exc()), 500
