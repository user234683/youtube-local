from youtube import common, settings
import sqlite3
import os

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
        cursor.execute('''SELECT video_id, title, time_published, description, channel_id, channel_name
                          FROM videos
                          INNER JOIN subscribed_channels on videos.uploader_id = subscribed_channels.id
                          ORDER BY time_published DESC
                          LIMIT ? OFFSET ?''', number, offset)
    except:
        connection.rollback()
        raise
    finally:
        connection.close()
