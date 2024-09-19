#!/usr/bin/python3

import json
import sys

from cloudcix_primitives import directorymain

cmd = sys.argv[1]

dir_name = "/etc/netns/mynetns/10.0.0.3/v1"

if len(sys.argv) > 2:
    dir_name = sys.argv[2]

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = directorymain.build(dir_name, "/etc/cloudcix/pod/configs/config.json")
if cmd == 'scrub':
    # static parameter because scrub issues a rm -rf
    status, msg = directorymain.scrub("/etc/netns/mynetns", "/etc/cloudcix/pod/configs/config.json")
if cmd == 'read':
    status, data, msg = directorymain.read(dir_name, "/etc/cloudcix/pod/configs/config.json")

print("Status: %s" %  status)
print()
print("Message:")
if type(msg) == list:
    for item in msg:
        print(item)
else:
    print(msg)

if data is not None:
    print()
    print("Data:")
    print(json.dumps(data, sort_keys=True, indent=4))
