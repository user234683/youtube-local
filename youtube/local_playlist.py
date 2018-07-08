import os.path
import json

playlists_directory = os.path.normpath("data/playlists")

def add_to_playlist(name, video_info_list):
    with open(os.path.join(playlists_directory, name), "a", encoding='utf-8') as file:
        for info in video_info_list:
            file.write(info + "\n")
        
        
def get_playlist_page(name):
    pass