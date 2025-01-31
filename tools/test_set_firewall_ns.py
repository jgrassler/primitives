#! /usr/bin/env python3

# stdlib
import sys
import json
# local
from cloudcix_primitives import set_firewall_ns

cmd = sys.argv[1] if len(sys.argv) > 1 else None
set_name = "IE_41"
namespace_name = "ns1100"
set_type = 'ipv4_addr'
set_elements = '8.8.8.8, 1.1.1.1, 192.168.0.1/24'
config_file = "/etc/cloudcix/pod/configs/config.json"

if len(sys.argv) > 2:
    namespace_name = sys.argv[2]
if len(sys.argv) > 3:
    set_name = sys.argv[3]
if len(sys.argv) > 4:
    set_type = sys.argv[4]
if len(sys.argv) > 5:
    set_elements = sys.argv[5]

status = None
msg = None
data = None

if cmd == 'build':
    status, msg = set_firewall_ns.build(namespace_name, set_name, set_type, config_file)
elif cmd == 'scrub':
    status, msg = set_firewall_ns.scrub(namespace_name, set_name, config_file)
elif cmd == 'update': 
    status, msg = set_firewall_ns.update(namespace_name, set_name, set_elements, config_file)
else:
    print(f'Unknown command: {cmd}')
    sys.exit(1)

print(f'Status: {status}')
print(f'\nMessage: {msg}')

if data is not None:
    print(f'\nData: {json.dumps(data, sort_keys=True, indent=4)}')