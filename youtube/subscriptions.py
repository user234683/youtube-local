from youtube import util, yt_data_extract, html_common, channel
import settings
from string import Template
import sqlite3
import os
import secrets
import datetime
import itertools
import time
import urllib
import socks, sockshandler

with open('yt_subscriptions_template.html', 'r', encoding='utf-8') as f:
    subscriptions_template = Template(f.read())


# https://stackabuse.com/a-sqlite-tutorial-with-python/

database_path = os.path.join(settings.data_dir, "subscriptions.sqlite")

def open_database():
    if not os.path.exists(settings.data_dir):
        os.makedirs(settings.data_dir)
    connection = sqlite3.connect(database_path)

    # Create tables if they don't exist
    try:
        cursor = connection.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS subscribed_channels (
                              id integer PRIMARY KEY,
                              channel_id text NOT NULL,
                              channel_name text NOT NULL,
                              time_last_checked integer
                          )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS videos (
                              id integer PRIMARY KEY,
                              uploader_id integer NOT NULL REFERENCES subscribed_channels(id) ON UPDATE CASCADE ON DELETE CASCADE,
                              video_id text NOT NULL,
                              title text NOT NULL,
                              duration text,
                              time_published integer NOT NULL,
                              description text
                          )''')
        connection.commit()
    except:
        connection.rollback()
        connection.close()
        raise

    return connection

def _subscribe(channels):
    ''' channels is a list of (channel_id, channel_name) '''

    # set time_last_checked to 0 on all channels being subscribed to
    channels = ( (channel_id, channel_name, 0) for channel_id, channel_name in channels)

    connection = open_database()
    try:
        cursor = connection.cursor()
        cursor.executemany("INSERT INTO subscribed_channels (channel_id, channel_name, time_last_checked) VALUES (?, ?, ?)", channels)
        connection.commit()
    except:
        connection.rollback()
        raise
    finally:
        connection.close()

def _unsubscribe(channel_ids):
    ''' channel_ids is a list of channel_ids '''
    connection = open_database()
    try:
        cursor = connection.cursor()
        cursor.executemany("DELETE FROM subscribed_channels WHERE channel_id=?", ((channel_id, ) for channel_id in channel_ids))
        connection.commit()
    except:
        connection.rollback()
        raise
    finally:
        connection.close()

def _get_videos(number, offset):
    connection = open_database()
    try:
        cursor = connection.cursor()
        db_videos = cursor.execute('''SELECT video_id, title, duration, channel_name
                          FROM videos
                          INNER JOIN subscribed_channels on videos.uploader_id = subscribed_channels.id
                          ORDER BY time_published DESC
                          LIMIT ? OFFSET ?''', (number, offset))

        for db_video in db_videos:
            yield {
                'id':   db_video[0],
                'title':    db_video[1],
                'duration': db_video[2],
                'author':   db_video[3],
            }
    except:
        connection.rollback()
        raise
    finally:
        connection.close()



units = {
    'year': 31536000,   # 365*24*3600
    'month': 2592000,   # 30*24*3600
    'week': 604800,     # 7*24*3600
    'day':  86400,      # 24*3600
    'hour': 3600,
    'minute': 60,
    'second': 1,
}
def youtube_timestamp_to_posix(dumb_timestamp):
    ''' Given a dumbed down timestamp such as 1 year ago, 3 hours ago,
         approximates the unix time (seconds since 1/1/1970) '''
    dumb_timestamp = dumb_timestamp.lower()
    now = time.time()
    if dumb_timestamp == "just now":
        return now
    split = dumb_timestamp.split(' ')
    number, unit = int(split[0]), split[1]
    if number > 1:
        unit = unit[:-1]    # remove s from end
    return now - number*units[unit]

def _get_upstream_videos(channel_id):
    videos = []

    json_channel_videos = channel.get_grid_items(channel.get_channel_tab(channel_id)[1]['response'])
    for json_video in json_channel_videos:
        info = yt_data_extract.renderer_info(json_video['gridVideoRenderer'])
        if 'description' not in info:
            info['description'] = ''
        info['time_published'] = youtube_timestamp_to_posix(info['published'])
        videos.append(info)
    return videos

def get_subscriptions_page(env, start_response):
    items_html = '''<nav class="item-grid">\n'''

    for item in _get_videos(30, 0):
        items_html += html_common.video_item_html(item, html_common.small_video_item_template)
    items_html += '''\n</nav>'''

    start_response('200 OK', [('Content-type','text/html'),])
    return subscriptions_template.substitute(
        header = html_common.get_header(),
        items = items_html,
        page_buttons = '',
    ).encode('utf-8')

def post_subscriptions_page(env, start_response):
    params = env['parameters']
    action = params['action'][0]
    if action == 'subscribe':
        if len(params['channel_id']) != len(params['channel_name']):
            start_response('400 Bad Request', ())
            return b'400 Bad Request, length of channel_id != length of channel_name'
        _subscribe(zip(params['channel_id'], params['channel_name']))

    elif action == 'unsubscribe':
        _unsubscribe(params['channel_id'])

    elif action == 'refresh':
        connection = open_database()
        try:
            cursor = connection.cursor()
            for uploader_id, channel_id in cursor.execute('''SELECT id, channel_id FROM subscribed_channels'''):
                db_videos = ( (uploader_id, info['id'], info['title'], info['duration'], info['time_published'], info['description']) for info in _get_upstream_videos(channel_id) )
                cursor.executemany('''INSERT INTO videos (uploader_id, video_id, title, duration, time_published, description) VALUES (?, ?, ?, ?, ?, ?)''', db_videos)

            cursor.execute('''UPDATE subscribed_channels SET time_last_checked = ?''', ( int(time.time()), ) )
            connection.commit()
        except:
            connection.rollback()
            raise
        finally:
            connection.close()

        start_response('303 See Other', [('Location', util.URL_ORIGIN + '/subscriptions'),] )
        return b''
    else:
        start_response('400 Bad Request', ())
        return b'400 Bad Request'
    start_response('204 No Content', ())
    return b''
