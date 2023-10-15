from youtube import util, yt_data_extract, channel, local_playlist, playlist
from youtube import yt_app
import settings

import sqlite3
import os
import time
import gevent
import json
import traceback
import contextlib
import defusedxml.ElementTree
import urllib
import math
import secrets
import collections
import calendar # bullshit! https://bugs.python.org/issue6280
import csv
import re

import flask
from flask import request


thumbnails_directory = os.path.join(settings.data_dir, "subscription_thumbnails")

# https://stackabuse.com/a-sqlite-tutorial-with-python/

database_path = os.path.join(settings.data_dir, "subscriptions.sqlite")

def open_database():
    if not os.path.exists(settings.data_dir):
        os.makedirs(settings.data_dir)
    connection = sqlite3.connect(database_path, check_same_thread=False)

    try:
        cursor = connection.cursor()
        cursor.execute('''PRAGMA foreign_keys = 1''')
        # Create tables if they don't exist
        cursor.execute('''CREATE TABLE IF NOT EXISTS subscribed_channels (
                              id integer PRIMARY KEY,
                              yt_channel_id text UNIQUE NOT NULL,
                              channel_name text NOT NULL,
                              time_last_checked integer DEFAULT 0,
                              next_check_time integer DEFAULT 0,
                              muted integer DEFAULT 0
                          )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS videos (
                              id integer PRIMARY KEY,
                              sql_channel_id integer NOT NULL REFERENCES subscribed_channels(id) ON UPDATE CASCADE ON DELETE CASCADE,
                              video_id text UNIQUE NOT NULL,
                              title text NOT NULL,
                              duration text,
                              time_published integer NOT NULL,
                              is_time_published_exact integer DEFAULT 0,
                              time_noticed integer NOT NULL,
                              description text,
                              watched integer default 0
                          )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS tag_associations (
                              id integer PRIMARY KEY,
                              tag text NOT NULL,
                              sql_channel_id integer NOT NULL REFERENCES subscribed_channels(id) ON UPDATE CASCADE ON DELETE CASCADE,
                              UNIQUE(tag, sql_channel_id)
                          )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS db_info (
                              version integer DEFAULT 1
                          )''')

        connection.commit()
    except:
        connection.rollback()
        connection.close()
        raise

    # https://stackoverflow.com/questions/19522505/using-sqlite3-in-python-with-with-keyword
    return contextlib.closing(connection)

def with_open_db(function, *args, **kwargs):
    with open_database() as connection:
        with connection as cursor:
            return function(cursor, *args, **kwargs)

def _is_subscribed(cursor, channel_id):
    result = cursor.execute('''SELECT EXISTS(
                                   SELECT 1
                                   FROM subscribed_channels
                                   WHERE yt_channel_id=?
                                   LIMIT 1
                               )''', [channel_id]).fetchone()
    return bool(result[0])

def is_subscribed(channel_id):
    if not os.path.exists(database_path):
        return False

    return with_open_db(_is_subscribed, channel_id)

def _subscribe(channels):
    ''' channels is a list of (channel_id, channel_name) '''
    channels = list(channels)
    with open_database() as connection:
        with connection as cursor:
            channel_ids_to_check = [channel[0] for channel in channels if not _is_subscribed(cursor, channel[0])]

            rows = ( (channel_id, channel_name, 0, 0) for channel_id, channel_name in channels)
            cursor.executemany('''INSERT OR IGNORE INTO subscribed_channels (yt_channel_id, channel_name, time_last_checked, next_check_time)
                                  VALUES (?, ?, ?, ?)''', rows)

    if settings.autocheck_subscriptions:
        # important that this is after the changes have been committed to database
        # otherwise the autochecker (other thread) tries checking the channel before it's in the database
        channel_names.update(channels)
        check_channels_if_necessary(channel_ids_to_check)

def delete_thumbnails(to_delete):
    for thumbnail in to_delete:
        try:
            video_id = thumbnail[0:-4]
            if video_id in existing_thumbnails:
                os.remove(os.path.join(thumbnails_directory, thumbnail))
                existing_thumbnails.remove(video_id)
        except Exception:
            print('Failed to delete thumbnail: ' + thumbnail)
            traceback.print_exc()

def _unsubscribe(cursor, channel_ids):
    ''' channel_ids is a list of channel_ids '''
    to_delete = []
    for channel_id in channel_ids:
        rows = cursor.execute('''SELECT video_id
                                 FROM videos
                                 WHERE sql_channel_id = (
                                     SELECT id
                                     FROM subscribed_channels
                                     WHERE yt_channel_id=?
                                 )''', (channel_id,)).fetchall()
        to_delete += [row[0] + '.jpg' for row in rows]

    gevent.spawn(delete_thumbnails, to_delete)
    cursor.executemany("DELETE FROM subscribed_channels WHERE yt_channel_id=?", ((channel_id, ) for channel_id in channel_ids))

def _get_videos(cursor, number_per_page, offset, tag = None):
    '''Returns a full page of videos with an offset, and a value good enough to be used as the total number of videos'''
    # We ask for the next 9 pages from the database
    # Then the actual length of the results tell us if there are more than 9 pages left, and if not, how many there actually are
    # This is done since there are only 9 page buttons on display at a time
    # If there are more than 9 pages left, we give a fake value in place of the real number of results if the entire database was queried without limit
    # This fake value is sufficient to get the page button generation macro to display 9 page buttons
    # If we wish to display more buttons this logic must change
    # We cannot use tricks with the sql id for the video since we frequently have filters and other restrictions in place on the results anyway
    # TODO: This is probably not the ideal solution
    if tag is not None:
        db_videos = cursor.execute('''SELECT video_id, title, duration, time_published, is_time_published_exact, channel_name, yt_channel_id
                                      FROM videos
                                      INNER JOIN subscribed_channels on videos.sql_channel_id = subscribed_channels.id
                                      INNER JOIN tag_associations on videos.sql_channel_id = tag_associations.sql_channel_id
                                      WHERE tag = ? AND muted = 0
                                      ORDER BY time_noticed DESC, time_published DESC
                                      LIMIT ? OFFSET ?''', (tag, number_per_page*9, offset)).fetchall()
    else:
        db_videos = cursor.execute('''SELECT video_id, title, duration, time_published, is_time_published_exact, channel_name, yt_channel_id
                                      FROM videos
                                      INNER JOIN subscribed_channels on videos.sql_channel_id = subscribed_channels.id
                                      WHERE muted = 0
                                      ORDER BY time_noticed DESC, time_published DESC
                                      LIMIT ? OFFSET ?''', (number_per_page*9, offset)).fetchall()

    pseudo_number_of_videos = offset + len(db_videos)

    videos = []
    for db_video in db_videos[0:number_per_page]:
        videos.append({
            'id':   db_video[0],
            'title':    db_video[1],
            'duration': db_video[2],
            'time_published': exact_timestamp(db_video[3]) if db_video[4] else posix_to_dumbed_down(db_video[3]),
            'author':   db_video[5],
            'author_id': db_video[6],
            'author_url': '/https://www.youtube.com/channel/' + db_video[6],
        })

    return videos, pseudo_number_of_videos




def _get_subscribed_channels(cursor):
    for item in cursor.execute('''SELECT channel_name, yt_channel_id, muted
                                  FROM subscribed_channels
                                  ORDER BY channel_name COLLATE NOCASE'''):
        yield item


def _add_tags(cursor, channel_ids, tags):
    pairs = [(tag, yt_channel_id) for tag in tags for yt_channel_id in channel_ids]
    cursor.executemany('''INSERT OR IGNORE INTO tag_associations (tag, sql_channel_id)
                          SELECT ?, id FROM subscribed_channels WHERE yt_channel_id = ? ''', pairs)


def _remove_tags(cursor, channel_ids, tags):
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

def _get_all_tags(cursor):
    return [row[0] for row in cursor.execute('''SELECT DISTINCT tag FROM tag_associations''')]

def _get_channel_names(cursor, channel_ids):
    ''' returns list of (channel_id, channel_name) '''
    result = []
    for channel_id in channel_ids:
        row = cursor.execute('''SELECT channel_name
                                FROM subscribed_channels
                                WHERE yt_channel_id = ?''', (channel_id,)).fetchone()
        result.append( (channel_id, row[0]) )
    return result


def _channels_with_tag(cursor, tag, order=False, exclude_muted=False, include_muted_status=False):
    ''' returns list of (channel_id, channel_name) '''

    statement = '''SELECT yt_channel_id, channel_name'''

    if include_muted_status:
        statement += ''', muted'''

    statement += '''
                   FROM subscribed_channels
                   WHERE subscribed_channels.id IN (
                       SELECT tag_associations.sql_channel_id FROM tag_associations WHERE tag=?
                   )
                '''
    if exclude_muted:
        statement += '''AND muted != 1\n'''
    if order:
        statement += '''ORDER BY channel_name COLLATE NOCASE'''

    return cursor.execute(statement, [tag]).fetchall()

def _schedule_checking(cursor, channel_id, next_check_time):
    cursor.execute('''UPDATE subscribed_channels SET next_check_time = ? WHERE yt_channel_id = ?''', [int(next_check_time), channel_id])

def _is_muted(cursor, channel_id):
    return bool(cursor.execute('''SELECT muted FROM subscribed_channels WHERE yt_channel_id=?''', [channel_id]).fetchone()[0])

units = collections.OrderedDict([
    ('year', 31536000),   # 365*24*3600
    ('month', 2592000),   # 30*24*3600
    ('week', 604800),     # 7*24*3600
    ('day',  86400),      # 24*3600
    ('hour', 3600),
    ('minute', 60),
    ('second', 1),
])
def youtube_timestamp_to_posix(dumb_timestamp):
    ''' Given a dumbed down timestamp such as 1 year ago, 3 hours ago,
         approximates the unix time (seconds since 1/1/1970) '''
    dumb_timestamp = dumb_timestamp.lower()
    now = time.time()
    if dumb_timestamp == "just now":
        return now
    split = dumb_timestamp.split(' ')
    quantifier, unit = int(split[0]), split[1]
    if quantifier > 1:
        unit = unit[:-1]    # remove s from end
    return now - quantifier*units[unit]

def posix_to_dumbed_down(posix_time):
    '''Inverse of youtube_timestamp_to_posix.'''
    delta = int(time.time() - posix_time)
    assert delta >= 0

    if delta == 0:
        return '0 seconds ago'

    for unit_name, unit_time in units.items():
        if delta >= unit_time:
            quantifier = round(delta/unit_time)
            if quantifier == 1:
                return '1 ' + unit_name + ' ago'
            else:
                return str(quantifier) + ' ' + unit_name + 's ago'
    else:
        raise Exception()

def exact_timestamp(posix_time):
    result = time.strftime('%I:%M %p %m/%d/%y', time.localtime(posix_time))
    if result[0] == '0':    # remove 0 infront of hour (like 01:00 PM)
        return result[1:]
    return result

try:
    existing_thumbnails = set(os.path.splitext(name)[0] for name in os.listdir(thumbnails_directory))
except FileNotFoundError:
    existing_thumbnails = set()


# --- Manual checking system. Rate limited in order to support very large numbers of channels to be checked ---
# Auto checking system plugs into this for convenience, though it doesn't really need the rate limiting

check_channels_queue = util.RateLimitedQueue()
checking_channels = set()

# Just to use for printing channel checking status to console without opening database
channel_names = dict()

def check_channel_worker():
    while True:
        channel_id = check_channels_queue.get()
        try:
            _get_upstream_videos(channel_id)
        except Exception:
            traceback.print_exc()
        finally:
            checking_channels.remove(channel_id)

for i in range(0,5):
    gevent.spawn(check_channel_worker)
# ----------------------------



# --- Auto checking system - Spaghetti code ---
def autocheck_dispatcher():
    '''Scans the auto_check_list. Sleeps until the earliest job is due, then adds that channel to the checking queue above. Can be sent a new job through autocheck_job_application'''
    while True:
        if len(autocheck_jobs) == 0:
            new_job = autocheck_job_application.get()
            autocheck_jobs.append(new_job)
        else:
            earliest_job_index = min(range(0, len(autocheck_jobs)), key=lambda index: autocheck_jobs[index]['next_check_time']) # https://stackoverflow.com/a/11825864
            earliest_job = autocheck_jobs[earliest_job_index]
            time_until_earliest_job = earliest_job['next_check_time'] - time.time()

            if time_until_earliest_job <= -5:   # should not happen unless we're running extremely slow
                print('ERROR: autocheck_dispatcher got job scheduled in the past, skipping and rescheduling: ' + earliest_job['channel_id'] + ', ' + earliest_job['channel_name'] + ', ' + str(earliest_job['next_check_time']))
                next_check_time = time.time() + 3600*secrets.randbelow(60)/60
                with_open_db(_schedule_checking, earliest_job['channel_id'], next_check_time)
                autocheck_jobs[earliest_job_index]['next_check_time'] = next_check_time
                continue

            # make sure it's not muted
            if with_open_db(_is_muted, earliest_job['channel_id']):
                del autocheck_jobs[earliest_job_index]
                continue

            if time_until_earliest_job > 0: # it can become less than zero (in the past) when it's set to go off while the dispatcher is doing something else at that moment
                try:
                    new_job = autocheck_job_application.get(timeout = time_until_earliest_job)  # sleep for time_until_earliest_job time, but allow to be interrupted by new jobs
                except gevent.queue.Empty: # no new jobs
                    pass
                else: # new job, add it to the list
                    autocheck_jobs.append(new_job)
                    continue

            # no new jobs, time to execute the earliest job
            channel_names[earliest_job['channel_id']] = earliest_job['channel_name']
            checking_channels.add(earliest_job['channel_id'])
            check_channels_queue.put(earliest_job['channel_id'])
            del autocheck_jobs[earliest_job_index]

dispatcher_greenlet = None
def start_autocheck_system():
    global autocheck_job_application
    global autocheck_jobs
    global dispatcher_greenlet

    # job application format: dict with keys (channel_id, channel_name, next_check_time)
    autocheck_job_application = gevent.queue.Queue() # only really meant to hold 1 item, just reusing gevent's wait and timeout machinery

    autocheck_jobs = [] # list of dicts with the keys (channel_id, channel_name, next_check_time). Stores all the channels that need to be autochecked and when to check them
    with open_database() as connection:
        with connection as cursor:
            now = time.time()
            for row in cursor.execute('''SELECT yt_channel_id, channel_name, next_check_time FROM subscribed_channels WHERE muted != 1''').fetchall():

                if row[2] is None:
                    next_check_time = 0
                else:
                    next_check_time = row[2]

                # expired, check randomly within the next hour
                # note: even if it isn't scheduled in the past right now, it might end up being if it's due soon and we dont start dispatching by then, see below where time_until_earliest_job is negative
                if next_check_time < now:
                    next_check_time = now + 3600*secrets.randbelow(60)/60
                    row = (row[0], row[1], next_check_time)
                    _schedule_checking(cursor, row[0], next_check_time)
                autocheck_jobs.append({'channel_id': row[0], 'channel_name': row[1], 'next_check_time': next_check_time})
    dispatcher_greenlet = gevent.spawn(autocheck_dispatcher)

def stop_autocheck_system():
    if dispatcher_greenlet is not None:
        dispatcher_greenlet.kill()

def autocheck_setting_changed(old_value, new_value):
    if new_value:
        start_autocheck_system()
    else:
        stop_autocheck_system()

settings.add_setting_changed_hook('autocheck_subscriptions',
    autocheck_setting_changed)
if settings.autocheck_subscriptions:
    start_autocheck_system()
# ----------------------------



def check_channels_if_necessary(channel_ids):
    for channel_id in channel_ids:
        if channel_id not in checking_channels:
            checking_channels.add(channel_id)
            check_channels_queue.put(channel_id)

def _get_atoma_feed(channel_id):
    url = 'https://www.youtube.com/feeds/videos.xml?channel_id=' + channel_id
    try:
        return util.fetch_url(url).decode('utf-8')
    except util.FetchError as e:
        # 404 is expected for terminated channels
        if e.code in ('404', '429'):
            return ''
        if e.code == '502':
            return str(e)
        raise

def _get_channel_videos_first_page(channel_id, channel_status_name):
    try:
        # First try the playlist method
        pl_json = playlist.get_videos(
            'UU' + channel_id[2:],
            1,
            include_shorts=settings.include_shorts_in_subscriptions,
            report_text=None
        )
        pl_info = yt_data_extract.extract_playlist_info(pl_json)
        if pl_info.get('items'):
            pl_info['items'] = pl_info['items'][0:30]
            return pl_info

        # Try the channel api method
        channel_json = channel.get_channel_first_page(channel_id=channel_id)
        channel_info = yt_data_extract.extract_channel_info(
            json.loads(channel_json), 'videos'
        )
        return channel_info
    except util.FetchError as e:
        if e.code == '429' and settings.route_tor:
            error_message = ('Error checking channel ' + channel_status_name
                + ': Youtube blocked the request because the'
                + ' Tor exit node is overutilized. Try getting a new exit node'
                + ' by using the New Identity button in the Tor Browser.')
            if e.ip:
                error_message += ' Exit node IP address: ' + e.ip
            print(error_message)
            return None
        elif e.code == '502':
            print('Error checking channel', channel_status_name + ':', str(e))
            return None
        raise

def _get_upstream_videos(channel_id):
    try:
        channel_status_name = channel_names[channel_id]
    except KeyError:
        channel_status_name = channel_id

    print("Checking channel: " + channel_status_name)

    tasks = (
        # channel page, need for video duration
        gevent.spawn(_get_channel_videos_first_page, channel_id,
                     channel_status_name),
        # need atoma feed for exact published time
        gevent.spawn(_get_atoma_feed, channel_id)
    )
    gevent.joinall(tasks)

    channel_info, feed = tasks[0].value, tasks[1].value

    # extract published times from atoma feed
    times_published = {}
    try:
        def remove_bullshit(tag):
            '''Remove XML namespace bullshit from tagname. https://bugs.python.org/issue18304'''
            if '}' in tag:
                return tag[tag.rfind('}')+1:]
            return tag

        def find_element(base, tag_name):
            for element in base:
                if remove_bullshit(element.tag) == tag_name:
                    return element
            return None

        root = defusedxml.ElementTree.fromstring(feed)
        assert remove_bullshit(root.tag) == 'feed'
        for entry in root:
            if (remove_bullshit(entry.tag) != 'entry'):
                continue

            # it's yt:videoId in the xml but the yt: is turned into a namespace which is removed by remove_bullshit
            video_id_element = find_element(entry, 'videoId')
            time_published_element = find_element(entry, 'published')
            assert video_id_element is not None
            assert time_published_element is not None

            time_published = int(calendar.timegm(time.strptime(time_published_element.text, '%Y-%m-%dT%H:%M:%S+00:00')))
            times_published[video_id_element.text] = time_published

    except AssertionError:
        print('Failed to read atoma feed for ' + channel_status_name)
        traceback.print_exc()
    except defusedxml.ElementTree.ParseError:
        print('Failed to read atoma feed for ' + channel_status_name)

    if channel_info is None: # there was an error
        return
    if channel_info['error']:
        print('Error checking channel ' + channel_status_name + ': ' + channel_info['error'])
        return

    videos = channel_info['items']
    for i, video_item in enumerate(videos):
        if not video_item.get('description'):
            video_item['description'] = ''
        else:
            video_item['description'] = ''.join(run.get('text', '') for run in video_item['description'])

        if video_item['id'] in times_published:
            video_item['time_published'] = times_published[video_item['id']]
            video_item['is_time_published_exact'] = True
        else:
            video_item['is_time_published_exact'] = False
            try:
                video_item['time_published'] = youtube_timestamp_to_posix(video_item['time_published']) - i  # subtract a few seconds off the videos so they will be in the right order
            except KeyError:
                print(video_item)

        video_item['channel_id'] = channel_id


    if len(videos) == 0:
        average_upload_period = 4*7*24*3600 # assume 1 month for channel with no videos
    elif len(videos) < 5:
        average_upload_period = int((time.time() - videos[len(videos)-1]['time_published'])/len(videos))
    else:
        average_upload_period = int((time.time() - videos[4]['time_published'])/5) # equivalent to averaging the time between videos for the last 5 videos

    # calculate when to check next for auto checking
    # add some quantization and randomness to make pattern analysis by Youtube slightly harder
    quantized_upload_period = average_upload_period - (average_upload_period % (4*3600)) + 4*3600   # round up to nearest 4 hours
    randomized_upload_period = quantized_upload_period*(1 + secrets.randbelow(50)/50*0.5) # randomly between 1x and 1.5x
    next_check_delay = randomized_upload_period/10    # check at 10x the channel posting rate. might want to fine tune this number
    next_check_time = int(time.time() + next_check_delay)

    with open_database() as connection:
        with connection as cursor:

            # calculate how many new videos there are
            existing_vids = set(row[0] for row in cursor.execute(
                '''SELECT video_id
                   FROM videos
                   INNER JOIN subscribed_channels
                       ON videos.sql_channel_id = subscribed_channels.id
                   WHERE yt_channel_id=?
                   ORDER BY time_published DESC
                   LIMIT 30''', [channel_id]).fetchall())

            # new videos the channel has uploaded since last time we checked
            number_of_new_videos = 0
            for video in videos:
                if video['id'] in existing_vids:
                    break
                number_of_new_videos += 1

            is_first_check = cursor.execute('''SELECT time_last_checked FROM subscribed_channels WHERE yt_channel_id=?''', [channel_id]).fetchone()[0] in (None, 0)
            time_videos_retrieved = int(time.time())
            rows = []
            for i, video_item in enumerate(videos):
                if (is_first_check
                        or number_of_new_videos > 6
                        or i >= number_of_new_videos):
                    # don't want a crazy ordering on first check or check in a long time, since we're ordering by time_noticed
                    # Last condition is for when the channel deleting videos
                    # causes new videos to appear at the end of the backlog.
                    # For instance, if we have 30 vids in the DB, and 1 vid
                    # that we previously saw has since been deleted,
                    # then a video we haven't seen before will appear as the
                    # 30th. Don't want this to be considered a newly noticed
                    # vid which would appear at top of subscriptions feed
                    time_noticed = video_item['time_published']
                else:
                    time_noticed = time_videos_retrieved
                rows.append((
                    video_item['channel_id'],
                    video_item['id'],
                    video_item['title'],
                    video_item['duration'],
                    video_item['time_published'],
                    video_item['is_time_published_exact'],
                    time_noticed,
                    video_item['description'],
                ))


            cursor.executemany('''INSERT OR IGNORE INTO videos (
                                      sql_channel_id,
                                      video_id,
                                      title,
                                      duration,
                                      time_published,
                                      is_time_published_exact,
                                      time_noticed,
                                      description
                                  )
                                  VALUES ((SELECT id FROM subscribed_channels WHERE yt_channel_id=?), ?, ?, ?, ?, ?, ?, ?)''', rows)
            cursor.execute('''UPDATE subscribed_channels
                              SET time_last_checked = ?, next_check_time = ?
                              WHERE yt_channel_id=?''', [int(time.time()), next_check_time, channel_id])

            if settings.autocheck_subscriptions:
                if not _is_muted(cursor, channel_id):
                    autocheck_job_application.put({'channel_id': channel_id, 'channel_name': channel_names[channel_id], 'next_check_time': next_check_time})

    if number_of_new_videos == 0:
        print('No new videos from ' + channel_status_name)
    elif number_of_new_videos == 1:
        print('1 new video from ' + channel_status_name)
    else:
        print(str(number_of_new_videos) + ' new videos from ' + channel_status_name)



def check_all_channels():
    with open_database() as connection:
        with connection as cursor:
            channel_id_name_list = cursor.execute('''SELECT yt_channel_id, channel_name
                                                     FROM subscribed_channels
                                                     WHERE muted != 1''').fetchall()

    channel_names.update(channel_id_name_list)
    check_channels_if_necessary([item[0] for item in channel_id_name_list])


def check_tags(tags):
    channel_id_name_list = []
    with open_database() as connection:
        with connection as cursor:
            for tag in tags:
                channel_id_name_list += _channels_with_tag(cursor, tag, exclude_muted=True)

    channel_names.update(channel_id_name_list)
    check_channels_if_necessary([item[0] for item in channel_id_name_list])


def check_specific_channels(channel_ids):
    with open_database() as connection:
        with connection as cursor:
            channel_id_name_list = []
            for channel_id in channel_ids:
                channel_id_name_list += cursor.execute('''SELECT yt_channel_id, channel_name
                                                          FROM subscribed_channels
                                                          WHERE yt_channel_id=?''', [channel_id]).fetchall()
    channel_names.update(channel_id_name_list)
    check_channels_if_necessary(channel_ids)


CHANNEL_ID_RE = re.compile(r'UC[-_\w]{22}')
@yt_app.route('/import_subscriptions', methods=['POST'])
def import_subscriptions():

    # check if the post request has the file part
    if 'subscriptions_file' not in request.files:
        #flash('No file part')
        return flask.redirect(util.URL_ORIGIN + request.full_path)
    file = request.files['subscriptions_file']
    # if user does not select file, browser also
    # submit an empty part without filename
    if file.filename == '':
        #flash('No selected file')
        return flask.redirect(util.URL_ORIGIN + request.full_path)


    mime_type = file.mimetype

    if mime_type == 'application/json':
        info = file.read().decode('utf-8')
        if info == '':
            return '400 Bad Request: File is empty', 400
        try:
            info = json.loads(info)
        except json.decoder.JSONDecodeError:
            traceback.print_exc()
            return '400 Bad Request: Invalid json file', 400

        channels = []
        try:
            if 'app_version_int' in info:   # NewPipe Format
                for item in info['subscriptions']:
                    # Other service, such as SoundCloud
                    if item.get('service_id', 0) != 0:
                        continue
                    channel_url = item['url']
                    channel_id_match = CHANNEL_ID_RE.search(channel_url)
                    if channel_id_match:
                        channel_id = channel_id_match.group(0)
                    else:
                        print('WARNING: Could not find channel id in url',
                              channel_url)
                        continue
                    channels.append((channel_id, item['name']))
            else:   # Old Google Takeout format
                for item in info:
                    snippet = item['snippet']
                    channel_id = snippet['resourceId']['channelId']
                    channels.append((channel_id, snippet['title']))
        except (KeyError, IndexError):
            traceback.print_exc()
            return '400 Bad Request: Unknown json structure', 400
    elif mime_type in ('application/xml', 'text/xml', 'text/x-opml'):
        file = file.read().decode('utf-8')
        try:
            root = defusedxml.ElementTree.fromstring(file)
            assert root.tag == 'opml'
            channels = []
            for outline_element in root[0][0]:
                if (outline_element.tag != 'outline') or ('xmlUrl' not in outline_element.attrib):
                    continue


                channel_name = outline_element.attrib['text']
                channel_rss_url = outline_element.attrib['xmlUrl']
                channel_id = channel_rss_url[channel_rss_url.find('channel_id=')+11:].strip()
                channels.append( (channel_id, channel_name) )

        except (AssertionError, IndexError, defusedxml.ElementTree.ParseError) as e:
            return '400 Bad Request: Unable to read opml xml file, or the file is not the expected format', 400
    elif mime_type in ('text/csv', 'application/vnd.ms-excel'):
        content = file.read().decode('utf-8')
        reader = csv.reader(content.splitlines())
        channels = []
        for row in reader:
            if not row or row[0].lower().strip() == 'channel id':
                continue
            elif len(row) > 1 and CHANNEL_ID_RE.fullmatch(row[0].strip()):
                channels.append( (row[0], row[-1]) )
            else:
                print('WARNING: Unknown row format:', row)
    else:
            error = 'Unsupported file format: ' + mime_type
            error += (' . Only subscription.json, subscriptions.csv files'
                      ' (from Google Takeouts)'
                      ' and XML OPML files exported from Youtube\'s'
                      ' subscription manager page are supported')
            return (flask.render_template('error.html', error_message=error),
                    400)

    _subscribe(channels)

    return flask.redirect(util.URL_ORIGIN + '/subscription_manager', 303)


@yt_app.route('/export_subscriptions', methods=['POST'])
def export_subscriptions():
    include_muted = request.values.get('include_muted') == 'on'
    with open_database() as connection:
        with connection as cursor:
            sub_list = []
            for channel_name, channel_id, muted in (
                    _get_subscribed_channels(cursor)):
                if muted and not include_muted:
                    continue
                if request.values['export_format'] == 'json_google_takeout':
                    sub_list.append({
                        'kind': 'youtube#subscription',
                        'snippet': {
                            'muted': bool(muted),
                            'resourceId': {
                                'channelId': channel_id,
                                'kind': 'youtube#channel',
                            },
                            'tags': _get_tags(cursor, channel_id),
                            'title': channel_name,
                        },
                    })
                elif request.values['export_format'] == 'json_newpipe':
                    sub_list.append({
                        'service_id': 0,
                        'url': 'https://www.youtube.com/channel/' + channel_id,
                        'name': channel_name,
                    })
                elif request.values['export_format'] == 'opml':
                    sub_list.append({
                        'channel_name': channel_name,
                        'channel_id': channel_id,
                    })
    date_time = time.strftime('%Y%m%d%H%M', time.localtime())
    if request.values['export_format'] == 'json_google_takeout':
        r = flask.Response(json.dumps(sub_list), mimetype='text/json')
        cd = 'attachment; filename="subscriptions_%s.json"' % date_time
        r.headers['Content-Disposition'] = cd
        return r
    elif request.values['export_format'] == 'json_newpipe':
        r = flask.Response(json.dumps({
            'app_version': '0.21.9',
            'app_version_int': 975,
            'subscriptions': sub_list,
        }), mimetype='text/json')
        file_name = 'newpipe_subscriptions_%s_youtube-local.json' % date_time
        cd = 'attachment; filename="%s"' % file_name
        r.headers['Content-Disposition'] = cd
        return r
    elif request.values['export_format'] == 'opml':
        r = flask.Response(
            flask.render_template('subscriptions.xml', sub_list=sub_list),
            mimetype='text/xml')
        cd = 'attachment; filename="subscriptions_%s.xml"' % date_time
        r.headers['Content-Disposition'] = cd
        return r
    else:
        return '400 Bad Request', 400


@yt_app.route('/subscription_manager', methods=['GET'])
def get_subscription_manager_page():
    group_by_tags = request.args.get('group_by_tags', '0') == '1'
    with open_database() as connection:
        with connection as cursor:
            if group_by_tags:
                tag_groups = []

                for tag in _get_all_tags(cursor):
                    sub_list = []
                    for channel_id, channel_name, muted in _channels_with_tag(cursor, tag, order=True, include_muted_status=True):
                        sub_list.append({
                            'channel_url': util.URL_ORIGIN + '/channel/' + channel_id,
                            'channel_name': channel_name,
                            'channel_id': channel_id,
                            'muted': muted,
                            'tags': [t for t in _get_tags(cursor, channel_id) if t != tag],
                        })

                    tag_groups.append( (tag, sub_list) )

                # Channels with no tags
                channel_list = cursor.execute('''SELECT yt_channel_id, channel_name, muted
                                                 FROM subscribed_channels
                                                 WHERE id NOT IN (
                                                     SELECT sql_channel_id FROM tag_associations
                                                 )
                                                 ORDER BY channel_name COLLATE NOCASE''').fetchall()
                if channel_list:
                    sub_list = []
                    for channel_id, channel_name, muted in channel_list:
                        sub_list.append({
                            'channel_url': util.URL_ORIGIN + '/channel/' + channel_id,
                            'channel_name': channel_name,
                            'channel_id': channel_id,
                            'muted': muted,
                            'tags': [],
                        })

                    tag_groups.append( ('No tags', sub_list) )
            else:
                sub_list = []
                for channel_name, channel_id, muted in _get_subscribed_channels(cursor):
                    sub_list.append({
                        'channel_url': util.URL_ORIGIN + '/channel/' + channel_id,
                        'channel_name': channel_name,
                        'channel_id': channel_id,
                        'muted': muted,
                        'tags': _get_tags(cursor, channel_id),
                    })




    if group_by_tags:
        return flask.render_template('subscription_manager.html',
            group_by_tags = True,
            tag_groups = tag_groups,
        )
    else:
        return flask.render_template('subscription_manager.html',
            group_by_tags = False,
            sub_list = sub_list,
        )

def list_from_comma_separated_tags(string):
    return [tag.strip() for tag in string.split(',') if tag.strip()]


@yt_app.route('/subscription_manager', methods=['POST'])
def post_subscription_manager_page():
    action = request.values['action']

    with open_database() as connection:
        with connection as cursor:
            if action == 'add_tags':
                _add_tags(cursor, request.values.getlist('channel_ids'), [tag.lower() for tag in list_from_comma_separated_tags(request.values['tags'])])
            elif action == 'remove_tags':
                _remove_tags(cursor, request.values.getlist('channel_ids'), [tag.lower() for tag in list_from_comma_separated_tags(request.values['tags'])])
            elif action == 'unsubscribe':
                _unsubscribe(cursor, request.values.getlist('channel_ids'))
            elif action == 'unsubscribe_verify':
                unsubscribe_list = _get_channel_names(cursor, request.values.getlist('channel_ids'))
                return flask.render_template('unsubscribe_verify.html', unsubscribe_list = unsubscribe_list)

            elif action == 'mute':
                cursor.executemany('''UPDATE subscribed_channels
                                      SET muted = 1
                                      WHERE yt_channel_id = ?''', [(ci,) for ci in request.values.getlist('channel_ids')])
            elif action == 'unmute':
                cursor.executemany('''UPDATE subscribed_channels
                                      SET muted = 0
                                      WHERE yt_channel_id = ?''', [(ci,) for ci in request.values.getlist('channel_ids')])
            else:
                flask.abort(400)

    return flask.redirect(util.URL_ORIGIN + request.full_path, 303)

@yt_app.route('/subscriptions', methods=['GET'])
@yt_app.route('/feed/subscriptions', methods=['GET'])
def get_subscriptions_page():
    page = int(request.args.get('page', 1))
    with open_database() as connection:
        with connection as cursor:
            tag = request.args.get('tag', None)
            videos, number_of_videos_in_db = _get_videos(cursor, 60, (page - 1)*60, tag)
            for video in videos:
                video['thumbnail'] = util.URL_ORIGIN + '/data/subscription_thumbnails/' + video['id'] + '.jpg'
                video['type'] = 'video'
                video['item_size'] = 'small'
                util.add_extra_html_info(video)

            tags = _get_all_tags(cursor)


            subscription_list = []
            for channel_name, channel_id, muted in _get_subscribed_channels(cursor):
                subscription_list.append({
                    'channel_url': util.URL_ORIGIN + '/channel/' + channel_id,
                    'channel_name': channel_name,
                    'channel_id': channel_id,
                    'muted': muted,
                })

    return flask.render_template('subscriptions.html',
        header_playlist_names = local_playlist.get_playlist_names(),
        videos = videos,
        num_pages = math.ceil(number_of_videos_in_db/60),
        parameters_dictionary = request.args,
        tags = tags,
        current_tag = tag,
        subscription_list = subscription_list,
    )

@yt_app.route('/subscriptions', methods=['POST'])
@yt_app.route('/feed/subscriptions', methods=['POST'])
def post_subscriptions_page():
    action = request.values['action']
    if action == 'subscribe':
        if len(request.values.getlist('channel_id')) != len(request.values.getlist('channel_name')):
            return '400 Bad Request, length of channel_id != length of channel_name', 400
        _subscribe(zip(request.values.getlist('channel_id'), request.values.getlist('channel_name')))

    elif action == 'unsubscribe':
        with_open_db(_unsubscribe, request.values.getlist('channel_id'))

    elif action == 'refresh':
        type = request.values['type']
        if type == 'all':
            check_all_channels()
        elif type == 'tag':
            check_tags(request.values.getlist('tag_name'))
        elif type == 'channel':
            check_specific_channels(request.values.getlist('channel_id'))
        else:
            flask.abort(400)
    else:
        flask.abort(400)

    return '', 204


@yt_app.route('/data/subscription_thumbnails/<thumbnail>')
def serve_subscription_thumbnail(thumbnail):
    '''Serves thumbnail from disk if it's been saved already. If not, downloads the thumbnail, saves to disk, and serves it.'''
    assert thumbnail[-4:] == '.jpg'
    video_id = thumbnail[0:-4]
    thumbnail_path = os.path.join(thumbnails_directory, thumbnail)

    if video_id in existing_thumbnails:
        try:
            f = open(thumbnail_path, 'rb')
        except FileNotFoundError:
            existing_thumbnails.remove(video_id)
        else:
            image = f.read()
            f.close()
            return flask.Response(image, mimetype='image/jpeg')

    url = "https://i.ytimg.com/vi/" + video_id + "/mqdefault.jpg"
    try:
        image = util.fetch_url(url, report_text="Saved thumbnail: " + video_id)
    except urllib.error.HTTPError as e:
        print("Failed to download thumbnail for " + video_id + ": " + str(e))
        abort(e.code)
    try:
        f = open(thumbnail_path, 'wb')
    except FileNotFoundError:
        os.makedirs(thumbnails_directory, exist_ok = True)
        f = open(thumbnail_path, 'wb')
    f.write(image)
    f.close()
    existing_thumbnails.add(video_id)

    return flask.Response(image, mimetype='image/jpeg')







