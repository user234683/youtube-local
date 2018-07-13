default_settings = '''route_tor = False
port_number = 80
allow_foreign_addresses = False
'''
exec(default_settings)
try:
    with open('settings.txt', 'r', encoding='utf-8') as file:
        exec(file.read())
except FileNotFoundError:
    with open('settings.txt', 'a', encoding='utf-8') as file:
        file.write(default_settings)