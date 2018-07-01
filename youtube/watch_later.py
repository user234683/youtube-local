import os.path
import json
watch_later_file = os.path.normpath("youtube/watch_later.txt")
def add_to_watch_later(video_info_list):
    with open(watch_later_file, "a", encoding='utf-8') as file:
        for info in video_info_list:
            file.write(info + "\n")
        
        
def get_watch_later_page():
    pass