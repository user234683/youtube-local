from youtube import common, settings, channel
import sqlite3
import os
import secrets
import datetime

# so as to not completely break on people who have updated but don't know of new dependency
try:
    import atoma
except ModuleNotFoundError:
    print('Error: atoma not installed, subscriptions will not work')

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
                              description text,
                          )''')
        connection.commit()
    except:
        connection.rollback()
        connection.close()
        raise

    return connection

def _subscribe(channel_id, channel_name):
    connection = open_database()
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO subscribed_channels (channel_id, name) VALUES (?, ?)", (channel_id, channel_name))
        connection.commit()
    except:
        connection.rollback()
        raise
    finally:
        connection.close()

def _unsubscribe(channel_id):
    connection = open_database()
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM subscribed_channels WHERE channel_id=?", (channel_id, ))
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
        cursor.execute('''SELECT video_id, title, duration, time_published, description, channel_id, channel_name
                          FROM videos
                          INNER JOIN subscribed_channels on videos.uploader_id = subscribed_channels.id
                          ORDER BY time_published DESC
                          LIMIT ? OFFSET ?''', number, offset)
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


weekdays = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
months = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
def _get_upstream_videos(channel_id, channel_name, time_last_checked):
    feed_url = "https://www.youtube.com/feeds/videos.xml?channel_id=" + channel_id
    headers = {}

    # randomly change time_last_checked up to one day earlier to make tracking harder
    time_last_checked = time_last_checked - secrets.randbelow(24*3600)

    # If-Modified-Since header: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/If-Modified-Since
    struct_time = time.gmtime(time_last_checked)
    weekday = weekdays[struct_time.tm_wday]     # dumb requirement
    month = months[struct_time.tm_mon - 1]
    headers['If-Modified-Since'] = time.strftime(weekday + ', %d ' + month + ' %Y %H:%M:%S GMT', struct_time)
    print(headers['If-Modified-Since'])


    headers['User-Agent'] = 'Python-urllib'     # Don't leak python version
    headers['Accept-Encoding'] = 'gzip, br'
    req = urllib.request.Request(url, headers=headers)
    if settings.route_tor:
        opener = urllib.request.build_opener(sockshandler.SocksiPyHandler(socks.PROXY_TYPE_SOCKS5, "127.0.0.1", 9150))
    else:
        opener = urllib.request.build_opener()
    response = opener.open(req, timeout=15)


    if response.getcode == '304':
        print('No new videos for ' + channel_id)
        return []


    content = response.read()
    print('Retrieved videos for ' + channel_id)
    content = common.decode_content(content, response.getheader('Content-Encoding', default='identity'))


    feed = atoma.parse_atom_bytes(content)
    atom_videos = {}
    for entry in feed.entries:
        video_id = entry.id_[9:]     # example of id_: yt:video:q6EoRBvdVPQ

        # standard names used in this program for purposes of html templating
        atom_videos[video_id] = {
            'title': entry.title.value,
            'author': entry.authors[0].name,
            #'description': '',              # Not supported by atoma
            #'duration': '',                 # Youtube's atom feeds don't provide it.. very frustrating
            'published':    entry.published.strftime('%m/%d/%Y'),
            'time_published':   int(entry.published.timestamp()),
        }


    # final list
    videos = []

    # Now check channel page to retrieve missing information for videos
    json_channel_videos = channel.get_grid_items(channel.get_channel_tab(channel_id)[1]['response'])
    for json_video in json_channel_videos:
        info = renderer_info(json_video)
        if info['id'] in atom_videos:
            info.update(atom_videos[info['id']])
        else:
            info['author'] = channel_name
            info['time published'] = youtube_timestamp_to_posix(info['published'])
        videos.append(info)
    return videos
