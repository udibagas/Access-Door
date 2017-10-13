import json
from pprint import pprint


with open('config.json') as config_file:
    config = json.load(config_file)

ip_address = config['database']['connection']['mysql']['host']

print(ip_address)
