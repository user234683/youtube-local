import os
import json

playlists_directory = os.path.normpath("data/playlists")

def add_to_playlist(name, video_info_list):
    with open(os.path.join(playlists_directory, name + ".txt"), "a", encoding='utf-8') as file:
        for info in video_info_list:
            file.write(info + "\n")
        
        
def get_playlist_page(name):
    pass

def get_playlist_names():
    for item in os.listdir(playlists_directory):
        name, ext = os.path.splitext(item)
        if ext == '.txt':
            yield name