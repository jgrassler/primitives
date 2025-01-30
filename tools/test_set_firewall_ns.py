#! /usr/bin/env python3

import sys
import json
from cloudcix_primitives import set_firewall_ns

cmd = sys.argv[1] if len(sys.argv) > 1 else None
set_name = "IE_41"
namespace_name = "ns1100"
config_file = "/etc/cloudcix/pod/configs/config.json"

if len(sys.argv) > 2:
    namespace_name = sys.argv[2]
if len(sys.argv) > 3:
    set_name = sys.argv[3]

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = set_firewall_ns.build(namespace_name, set_name, 'ipv4_addr', config_file)
elif cmd == 'scrub':
    status, msg = set_firewall_ns.scrub(namespace_name, set_name, config_file)
elif cmd == 'update': 
    status, msg = set_firewall_ns.update(namespace_name, set_name, '8.8.8.8, 1.1.1.1', config_file)
else:
    print(f'Unknown command: {cmd}')
    sys.exit(1)

print(f'Status: {status}')
print(f'\nMessage: {msg}')

if data is not None:
    print(f'\nData: {json.dumps(data, sort_keys=True, indent=4)}')