import urllib

with open("subscriptions.txt", 'r', encoding='utf-8') as file:
    subscriptions = file.read()
    
# Line format: "channel_id channel_name"
# Example:
# UCYO_jab_esuFRV4b17AJtAw 3Blue1Brown

subscriptions = ((line[0:24], line[25: ]) for line in subscriptions.splitlines())

def get_new_videos():
    for channel_id, channel_name in subscriptions:
        



def get_subscriptions_page():
