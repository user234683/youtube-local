import flask
yt_app = flask.Flask(__name__)
yt_app.url_map.strict_slashes = False

@yt_app.route('/')
def homepage():
    return flask.render_template('home.html', title="Youtube local")
