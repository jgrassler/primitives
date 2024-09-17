# stdlib
import ipaddress
import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple
# libs
from jinja2 import Environment, meta, FileSystemLoader, Template
# local
from exceptions import (
    CouldNotFindPodNets,
    InvalidPodNetPrivate,
    InvalidPodNetMgmt,
    InvalidPodNetOOB,
    InvalidPodNetPublic,
    InvalidPodNetIPv4CPE,
    InvalidPodNetMgmtIPv6,
)


__all__ = [
    'check_template_data',
    'JINJA_ENV',
    'primitives_directory',
]


primitives_directory = os.path.dirname(os.path.abspath(__file__))
JINJA_ENV = Environment(
    loader=FileSystemLoader(f'{primitives_directory}/templates'),
    trim_blocks=True,
)


def check_template_data(template_data: Dict[str, Any], template: Template) -> Tuple[bool, str]:
    """
    Verifies for any key in template_data is missing.
    :param template_data: dictionary object that must have all the template_keys.
    :param template: The template to be verified
    :return: tuple of boolean flag, success and the error string if any
    """
    with open(str(template.filename), 'r') as fp:
        template_source = fp.read()

    parsed = JINJA_ENV.parse(source=template_source)
    required_keys = meta.find_undeclared_variables(parsed)
    err = ''
    for k in required_keys:
        if k not in template_data:
            err += f'Key `{k}` not found in template data.\n'

    success = '' == err
    return success, err


def load_pod_config(config_file=None, prefix=4000) -> Dict[str, Any]:
    """
    Checks for pod config.json from supplied config_filepath or the current working directory, 
    loads into a json object and returns the object
    :return data: object with podnet config
    """

    messages = {
      10: 'Config file {config_file} loaded.',
      11: 'Failed to open {config_file}: ',
      12: 'Failed to parse {config_file}: ',
      13: 'Failed to get `ipv6_subnet from config_file.',
      14: 'Invalid value for `ipv6_subnet` from config file {config_file}',
      15: 'Failed to get `podnet_a_enabled` from config file {config_file}',
      16: 'Failed to get `podnet_b_enabled` from config file {config_file}',
      17: 'Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
      18: 'Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
      19: 'Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'


    config_data = {
      'raw': None,
      'processed': None
    }

    # Load config from config_file
    try:
        with Path(config_file).open('r') as file:
            config['file'] = json.load(file)
    except OSError as e:
            return False, config_data, messages[prefix + 11] + e.__str__()
    except Exception as e:
            return False, config_data, messages[prefix + 12] + e.__str__()

    config_data['raw'] = config

    # Get the ipv6_subnet from config_file
    ipv6_subnet = config.get('ipv6_subnet', None)
    if ipv6_subnet is None:
        return False, config_data, ("%d: " % prefix + 13) + messages[13]
    # Verify the ipv6_subnet value
    try:
        ipaddress.ip_network(ipv6_subnet)
    except ValueError:
        return False, config_data, messages[14]

    # Get the PodNet Mgmt ips from ipv6_subnet
    config['processed']['podnet_a'] = f'{ipv6_subnet.split("/")[0]}10:0:2'
    config['processed']['podnet_b'] = f'{ipv6_subnet.split("/")[0]}10:0:3'

    # Get `podnet_a_enabled` and `podnet_b_enabled`
    podnet_a_enabled = config.get('podnet_a_enabled', None)
    if podnet_a_enabled is None:
        return False, config_data, ("%d: " % prefix + 15) + messages[15]
    podnet_b_enabled = config.get('podnet_b_enabled', None)
    if podnet_a_enabled is None:
        return False, config_data, ("%d: " % prefix + 16) + messages[16]

    # Determine enabled and disabled PodNet
    if podnet_a_enabled is True and podnet_b_enabled is False:
        enabled = podnet_a
        disabled = podnet_b
    elif podnet_a_enabled is False and podnet_b_enabled is True:
        enabled = podnet_b
        disabled = podnet_a
    elif podnet_a_enabled is True and podnet_b_enabled is True:
        return False, config_data, ("%d: " % prefix + 17) + messages[17]
    elif podnet_a_enabled is False and podnet_b_enabled is False:
        return False, config_data, ("%d: " % prefix + 18) + messages[18]
    else:
        return False, config_data, ("%d: " % prefix + 19) + messages[19]

    config_data['processed']['enabled'] = enabled
    config_data['processed']['disabled'] = disabled

    return True, config_data, ("%d: " % prefix + 10) + messages[10]

def get_podnets(config_filepath):
    data = load_pod_config(config_filepath)
    podnets = [
        value for key, value in data.items() if key in ['podnet_1', 'podnet_2']
    ]
    if len(podnets) == 0:
        raise CouldNotFindPodNets
    for podnet in podnets:
        if podnet.get('mgmt', '') == '':
            raise InvalidPodNetMgmt
        if podnet.get('oob', '') == '':
            raise InvalidPodNetOOB
        if podnet.get('private', '') == '':
            raise InvalidPodNetPrivate
        if podnet.get('public', '') == '':
            raise InvalidPodNetPublic
        if podnet.get('ipv4_cpe', '') == '':
            raise InvalidPodNetIPv4CPE
    return podnets


def get_mgmt_ipv6(mgmt):
    if mgmt in ['', None]:
        raise InvalidPodNetMgmt
    mgmt_ipv6 = ''
    for ip in mgmt['ips']:
        address = str(ip['network_address'])
        if ipaddress.ip_address(address).version == 6:
            mgmt_ipv6 = address
    if mgmt_ipv6 == '':
        raise InvalidPodNetMgmtIPv6
    return mgmt_ipv6
