import flask
yt_app = flask.Flask(__name__)
yt_app.url_map.strict_slashes = False
