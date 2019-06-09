from youtube import util, yt_data_extract, html_common, channel
import settings
from string import Template
import sqlite3
import os
import time
import gevent
import html
import json
import traceback
import contextlib

with open('yt_subscriptions_template.html', 'r', encoding='utf-8') as f:
    subscriptions_template = Template(f.read())

with open('yt_subscription_manager_template.html', 'r', encoding='utf-8') as f:
    subscription_manager_template = Template(f.read())


thumbnails_directory = os.path.join(settings.data_dir, "subscription_thumbnails")

# https://stackabuse.com/a-sqlite-tutorial-with-python/

database_path = os.path.join(settings.data_dir, "subscriptions.sqlite")

def open_database():
    if not os.path.exists(settings.data_dir):
        os.makedirs(settings.data_dir)
    connection = sqlite3.connect(database_path, check_same_thread=False)

    # Create tables if they don't exist
    try:
        cursor = connection.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS subscribed_channels (
                              id integer PRIMARY KEY,
                              yt_channel_id text UNIQUE NOT NULL,
                              channel_name text NOT NULL,
                              time_last_checked integer
                          )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS videos (
                              id integer PRIMARY KEY,
                              sql_channel_id integer NOT NULL REFERENCES subscribed_channels(id) ON UPDATE CASCADE ON DELETE CASCADE,
                              video_id text UNIQUE NOT NULL,
                              title text NOT NULL,
                              duration text,
                              time_published integer NOT NULL,
                              description text
                          )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS tag_associations (
                              id integer PRIMARY KEY,
                              tag text NOT NULL,
                              sql_channel_id integer NOT NULL REFERENCES subscribed_channels(id) ON UPDATE CASCADE ON DELETE CASCADE,
                              UNIQUE(tag, sql_channel_id)
                          )''')

        connection.commit()
    except:
        connection.rollback()
        connection.close()
        raise

    # https://stackoverflow.com/questions/19522505/using-sqlite3-in-python-with-with-keyword
    return contextlib.closing(connection)

def _subscribe(channels):
    ''' channels is a list of (channel_id, channel_name) '''

    # set time_last_checked to 0 on all channels being subscribed to
    channels = ( (channel_id, channel_name, 0) for channel_id, channel_name in channels)

    with open_database() as connection:
        with connection as cursor:
            cursor.executemany('''INSERT OR IGNORE INTO subscribed_channels (yt_channel_id, channel_name, time_last_checked)
                                  VALUES (?, ?, ?)''', channels)

# TODO: delete thumbnails
def _unsubscribe(channel_ids):
    ''' channel_ids is a list of channel_ids '''
    with open_database() as connection:
        with connection as cursor:
            cursor.executemany("DELETE FROM subscribed_channels WHERE yt_channel_id=?", ((channel_id, ) for channel_id in channel_ids))

def _get_videos(number, offset):
    with open_database() as connection:
        with connection as cursor:
            db_videos = cursor.execute('''SELECT video_id, title, duration, channel_name
                                          FROM videos
                                          INNER JOIN subscribed_channels on videos.sql_channel_id = subscribed_channels.id
                                          ORDER BY time_published DESC
                                          LIMIT ? OFFSET ?''', (number, offset))

            for db_video in db_videos:
                yield {
                    'id':   db_video[0],
                    'title':    db_video[1],
                    'duration': db_video[2],
                    'author':   db_video[3],
                }

def _get_subscribed_channels():
    with open_database() as connection:
        with connection as cursor:
            for item in cursor.execute('''SELECT channel_name, yt_channel_id
                                          FROM subscribed_channels
                                          ORDER BY channel_name'''):
                yield item


def _add_tags(channel_ids, tags):
    with open_database() as connection:
        with connection as cursor:
            pairs = [(tag, yt_channel_id) for tag in tags for yt_channel_id in channel_ids]
            cursor.executemany('''INSERT OR IGNORE INTO tag_associations (tag, sql_channel_id)
                                  SELECT ?, id FROM subscribed_channels WHERE yt_channel_id = ? ''', pairs)


def _remove_tags(channel_ids, tags):
    with open_database() as connection:
        with connection as cursor:
            pairs = [(tag, yt_channel_id) for tag in tags for yt_channel_id in channel_ids]
            cursor.executemany('''DELETE FROM tag_associations
                                  WHERE tag = ? AND sql_channel_id = (
                                      SELECT id FROM subscribed_channels WHERE yt_channel_id = ?
                                   )''', pairs)



def _get_tags(cursor, channel_id):
    return [row[0] for row in cursor.execute('''SELECT tag
                                                FROM tag_associations
                                                WHERE sql_channel_id = (
                                                    SELECT id FROM subscribed_channels WHERE yt_channel_id = ?
                                                )''', (channel_id,))]

def _get_all_tags():
    with open_database() as connection:
        with connection as cursor:
            return [row[0] for row in cursor.execute('''SELECT DISTINCT tag FROM tag_associations''')]

def _get_channel_names(channel_ids):
    ''' returns list of (channel_id, channel_name) '''
    with open_database() as connection:
        with connection as cursor:
            result = []
            for channel_id in channel_ids:
                row = cursor.execute('''SELECT channel_name
                                        FROM subscribed_channels
                                        WHERE yt_channel_id = ?''', (channel_id,)).fetchone()
                result.append( (channel_id, row[0]) )
            return result


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


try:
    existing_thumbnails = set(os.path.splitext(name)[0] for name in os.listdir(thumbnails_directory))
except FileNotFoundError:
    existing_thumbnails = set()


thumbnails_queue = util.RateLimitedQueue()
check_channels_queue = util.RateLimitedQueue()


# Use this to mark a thumbnail acceptable to be retrieved at the request of the browser
# can't simply check if it's in the queue because items are removed when the download starts, not when it finishes
downloading_thumbnails = set()

checking_channels = set()

# Just to use for printing channel checking status to console without opening database
channel_names = dict()

def download_thumbnail_worker():
    while True:
        video_id = thumbnails_queue.get()
        try:
            success = util.download_thumbnail(thumbnails_directory, video_id)
            if success:
                existing_thumbnails.add(video_id)
        except Exception:
            traceback.print_exc()
        finally:
            downloading_thumbnails.remove(video_id)

def check_channel_worker():
    while True:
        channel_id = check_channels_queue.get()
        try:
            _get_upstream_videos(channel_id)
        finally:
            checking_channels.remove(channel_id)

for i in range(0,5):
    gevent.spawn(download_thumbnail_worker)
    gevent.spawn(check_channel_worker)






def download_thumbnails_if_necessary(thumbnails):
    for video_id in thumbnails:
        if video_id not in existing_thumbnails and video_id not in downloading_thumbnails:
            downloading_thumbnails.add(video_id)
            thumbnails_queue.put(video_id)

def check_channels_if_necessary(channel_ids):
    for channel_id in channel_ids:
        if channel_id not in checking_channels:
            checking_channels.add(channel_id)
            check_channels_queue.put(channel_id)



def _get_upstream_videos(channel_id):
    try:
        print("Checking channel: " + channel_names[channel_id])
    except KeyError:
        print("Checking channel " + channel_id)

    videos = []

    json_channel_videos = channel.get_grid_items(channel.get_channel_tab(channel_id)[1]['response'])
    for i, json_video in enumerate(json_channel_videos):
        info = yt_data_extract.renderer_info(json_video['gridVideoRenderer'])
        if 'description' not in info:
            info['description'] = ''
        try:
            info['time_published'] = youtube_timestamp_to_posix(info['published']) - i  # subtract a few seconds off the videos so they will be in the right order
        except KeyError:
            print(info)
        videos.append((channel_id, info['id'], info['title'], info['duration'], info['time_published'], info['description']))

    now = time.time()
    download_thumbnails_if_necessary(video[1] for video in videos if (now - video[4]) < 30*24*3600) # Don't download thumbnails from videos older than a month

    with open_database() as connection:
        with connection as cursor:
            cursor.executemany('''INSERT OR IGNORE INTO videos (sql_channel_id, video_id, title, duration, time_published, description)
                                  VALUES ((SELECT id FROM subscribed_channels WHERE yt_channel_id=?), ?, ?, ?, ?, ?)''', videos)
            cursor.execute('''UPDATE subscribed_channels
                              SET time_last_checked = ?
                              WHERE yt_channel_id=?''', [int(time.time()), channel_id])


def check_all_channels():
    with open_database() as connection:
        with connection as cursor:
            channel_id_name_list = cursor.execute('''SELECT yt_channel_id, channel_name FROM subscribed_channels''').fetchall()

    channel_names.update(channel_id_name_list)
    check_channels_if_necessary([item[0] for item in channel_id_name_list])


def check_tags(tags):
    channel_id_name_list = []
    with open_database() as connection:
        with connection as cursor:
            for tag in tags:
                channel_id_name_list += cursor.execute('''SELECT yt_channel_id, channel_name
                                                          FROM subscribed_channels
                                                          WHERE subscribed_channels.id IN (
                                                              SELECT tag_associations.sql_channel_id FROM tag_associations WHERE tag=?
                                                          )''', [tag]).fetchall()
    channel_names.update(channel_id_name_list)
    check_channels_if_necessary([item[0] for item in channel_id_name_list])


def check_specific_channels(channel_ids):
    with open_database() as connection:
        with connection as cursor:
            for channel_id in channel_ids:
                channel_id_name_list += cursor.execute('''SELECT yt_channel_id, channel_name
                                                          FROM subscribed_channels
                                                          WHERE yt_channel_id=?''', [channel_id]).fetchall()
    channel_names.update(channel_id_name_list)
    check_channels_if_necessary(channel_ids)




def import_subscriptions(env, start_response):
    content_type = env['parameters']['subscriptions_file'][0]
    file = env['parameters']['subscriptions_file'][1]

    file = file.decode('utf-8')

    if content_type == 'application/json':
        try:
            file = json.loads(file)
        except json.decoder.JSONDecodeError:
            traceback.print_exc()
            start_response('400 Bad Request', () )
            return b'400 Bad Request: Invalid json file'

        try:
            channels = ( (item['snippet']['resourceId']['channelId'], item['snippet']['title']) for item in file)
        except (KeyError, IndexError):
            traceback.print_exc()
            start_response('400 Bad Request', () )
            return b'400 Bad Request: Unknown json structure'
    else:
        raise NotImplementedError()

    _subscribe(channels)

    start_response('303 See Other', [('Location', util.URL_ORIGIN + '/subscription_manager'),] )
    return b''



sub_list_item_template = Template('''
<li>
    <a href="$channel_url" class="sub-list-item-name" title="$channel_name">$channel_name</a>
    <span class="tag-list">$tags</span>
    <input class="sub-list-checkbox" name="channel_ids" value="$channel_id" form="subscription-manager-form" type="checkbox">
</li>''')

def get_subscription_manager_page(env, start_response):

    sub_list_html = ''
    with open_database() as connection:
        with connection as cursor:
            for channel_name, channel_id in _get_subscribed_channels():
                sub_list_html += sub_list_item_template.substitute(
                    channel_url = util.URL_ORIGIN + '/channel/' + channel_id,
                    channel_name = html.escape(channel_name),
                    channel_id = channel_id,
                    tags = ', '.join(_get_tags(cursor, channel_id)),
                )



    start_response('200 OK', [('Content-type','text/html'),])
    return subscription_manager_template.substitute(
        header = html_common.get_header(),
        sub_list = sub_list_html,
        page_buttons = '',
    ).encode('utf-8')

def list_from_comma_separated_tags(string):
    tags = []
    prev_comma = -1
    next_comma = string.find(',')
    while next_comma != -1:
        tag = string[prev_comma+1:next_comma].strip()
        if tag:
            tags.append(tag)

        prev_comma = next_comma
        next_comma = string.find(',', prev_comma+1)

    last_tag = string[prev_comma+1:].strip()
    if last_tag:
        tags.append(last_tag)
    return tags


unsubscribe_list_item_template = Template('''
<li><a href="$channel_url" title="$channel_name">$channel_name</a></li>''')
def post_subscription_manager_page(env, start_response):
    params = env['parameters']
    action = params['action'][0]

    if action == 'add_tags':
        _add_tags(params['channel_ids'], [tag.lower() for tag in list_from_comma_separated_tags(params['tags'][0])])
    elif action == 'remove_tags':
        _remove_tags(params['channel_ids'], [tag.lower() for tag in list_from_comma_separated_tags(params['tags'][0])])
    elif action == 'unsubscribe':
        _unsubscribe(params['channel_ids'])
    elif action == 'unsubscribe_verify':
        page = '''
        <span>Are you sure you want to unsubscribe from these channels?</span>
        <form class="subscriptions-import-form" action="/youtube.com/subscription_manager" method="POST">'''

        for channel_id in params['channel_ids']:
            page += '<input type="hidden" name="channel_ids" value="' + channel_id + '">\n'

        page += '''
            <input type="hidden" name="action" value="unsubscribe">
            <input type="submit" value="Yes, unsubscribe">
        </form>
        <ul>'''
        for channel_id, channel_name in _get_channel_names(params['channel_ids']):
            page += unsubscribe_list_item_template.substitute(
                channel_url = util.URL_ORIGIN + '/channel/' + channel_id,
                channel_name = html.escape(channel_name),
            )
        page += '''</ul>'''

        start_response('200 OK', [('Content-type','text/html'),])
        return html_common.yt_basic_template.substitute(
            page_title = 'Unsubscribe?',
            style = '',
            header = html_common.get_header(),
            page = page,
        ).encode('utf-8')
    else:
        start_response('400 Bad Request', ())
        return b'400 Bad Request'

    start_response('303 See Other', [('Location', util.URL_ORIGIN + '/subscription_manager'),] )
    return b''



sidebar_tag_item_template = Template('''
<li>
    <span class="sidebar-item-name">$tag_name</span>
    <form method="POST" class="sidebar-item-refresh">
        <input type="submit" value="Check">
        <input type="hidden" name="action" value="refresh">
        <input type="hidden" name="type" value="tag">
        <input type="hidden" name="tag_name" value="$tag_name">
    </form>
</li>''')


sidebar_channel_item_template = Template('''
<li>
    <a href="$channel_url" class="sidebar-item-name" title="$channel_name">$channel_name</a>
    <form method="POST" class="sidebar-item-refresh">
        <input type="submit" value="Check">
        <input type="hidden" name="action" value="refresh">
        <input type="hidden" name="type" value="channel">
        <input type="hidden" name="channel_id" value="$channel_id">
    </form>
</li>''')

def get_subscriptions_page(env, start_response):
    items_html = '''<nav class="item-grid">\n'''

    for item in _get_videos(30, 0):
        if item['id'] in downloading_thumbnails:
            item['thumbnail'] = util.get_thumbnail_url(item['id'])
        else:
            item['thumbnail'] = util.URL_ORIGIN + '/data/subscription_thumbnails/' + item['id'] + '.jpg'
        items_html += html_common.video_item_html(item, html_common.small_video_item_template)
    items_html += '''\n</nav>'''


    tag_list_html = ''
    for tag_name in _get_all_tags():
        tag_list_html += sidebar_tag_item_template.substitute(tag_name = tag_name)


    sub_list_html = ''
    for channel_name, channel_id in _get_subscribed_channels():
        sub_list_html += sidebar_channel_item_template.substitute(
            channel_url = util.URL_ORIGIN + '/channel/' + channel_id,
            channel_name = html.escape(channel_name),
            channel_id = channel_id,
        )



    start_response('200 OK', [('Content-type','text/html'),])
    return subscriptions_template.substitute(
        header = html_common.get_header(),
        items = items_html,
        tags = tag_list_html,
        sub_list = sub_list_html,
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
        type = params['type'][0]
        if type == 'all':
            check_all_channels()
        elif type == 'tag':
            check_tags(params['tag_name'])
        elif type == 'channel':
            check_specific_channels(params['channel_id'])
        else:
            start_response('400 Bad Request', ())
            return b'400 Bad Request'

        start_response('204 No Content', ())
        return b''
    else:
        start_response('400 Bad Request', ())
        return b'400 Bad Request'
    start_response('204 No Content', ())
    return b''
