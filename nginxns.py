"""
Primitive to Build, Read and Scrub nginx for cloud-init userdata/metadata delivery on PodNet HA
"""
# 3rd party modules
import jinja2
# stdlib
import json
import ipaddress
import os
from pathlib import Path
from textwrap import dedent
from typing import Tuple
# lib
from cloudcix.rcc import comms_ssh, CouldNotConnectException
# local


__all__ = [
    'build',
    'read',
    'scrub',
]

SUCCESS_CODE = 0

template_path = os.path.join(os.path.dirname(__file__), 'templates', __name__.split(".").pop())

def build(
        domain_path: str,
        domain: str,
        interfaces: dict,
        config_file=None,
        userdata=""
) -> Tuple[bool, str]:
    """
    description:
        Configures and launches an nginx instance for serving cloud-init userdata/metadata from a VRF network name space

    parameters:
        namespace:
            description: VRF network name space's identifier, such as 'VRF453
            type: string
            required: true
        config_file:
            description: path to the config.json file
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """

    nginx_config_path = '/etc/netns/{namespace}/nginx.conf'

    # Define message
    messages = {
        1000: f'1000: Successfully created and {nginx_config_path} and launched nginx process on both PodNet nodes.',
        2111: f'2011: Config file {config_file} loaded.',
        3011: f'3011: Failed to load config file {config_file}, It does not exist.',
        3012: f'3012: Failed to get `ipv6_subnet` from config file {config_file}',
        3013: f'3013: Invalid value for `ipv6_subnet` from config file {config_file}',
        3014: f'3014: Failed to get `podnet_a_enabled` from config file {config_file}',
        3015: f'3015: Failed to get `podnet_b_enabled` from config file {config_file}',
        3016: f'3016: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3017: f'3017: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3018: f'3018: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3019: f'3019: Failed to render jinja2 template for {nginx_conf_path}',
        3021: f'3021: Failed to connect to the enabled PodNet from the config file {config_file} for create_config_payload',
        3022: f'3022: Failed to create config file {nginx_config_path} on the enabled PodNet. Payload exited with status ',
        3023: f'3023: Failed to connect to the enabled PodNet from the config file {config_file} for launch_nginx_payload',
        3023: f'3024: Failed to launch nginx on the enabled PodNet. Payload exited with status ',
        3031: f'3031: Successfully created {nginx_config_path} and launched nginx on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for create_config_payload.',
        3032: f'3032: Successfully created {nginx_config_path} and launched nginx on enabled PodNet but failed to create {nginx_config_path} on the disabled PodNet. '
               'Payload exited with status ',
        3033: f'3033: Successfully created {nginx_config_path} on both PodNet nodes and launched nginx on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for launch_nginx_payload.',
        3034: f'3034: Successfully created {nginx_config_path} on both PodNet nodes and launched nginx on enabled PodNet but failed to launch nginx on the disabled PodNet. '
               'Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/etc/cloudcix/pod/configs/config.json'

    # Get load config from config_file
    if not Path(config_file).exists():
        return False, messages[3011]
    with Path(config_file).open('r') as file:
        config = json.load(file)

    # Get the ipv6_subnet from config_file
    ipv6_subnet = config.get('ipv6_subnet', None)
    if ipv6_subnet is None:
        return False, messages[3012]
    # Verify the ipv6_subnet value
    try:
        ipaddress.ip_network(ipv6_subnet)
    except ValueError:
        return False, messages[3013]

    # Get the PodNet Mgmt ips from ipv6_subnet
    podnet_a = f'{ipv6_subnet.split("/")[0]}10:0:2'
    podnet_b = f'{ipv6_subnet.split("/")[0]}10:0:3'

    # Get `podnet_a_enabled` and `podnet_b_enabled`
    podnet_a_enabled = config.get('podnet_a_enabled', None)
    if podnet_a_enabled is None:
        return False, messages[3014]
    podnet_b_enabled = config.get('podnet_b_enabled', None)
    if podnet_a_enabled is None:
        return False, messages[3015]

    # First run on enabled PodNet
    if podnet_a_enabled is True and podnet_b_enabled is False:
        enabled = podnet_a
        disabled = podnet_b
    elif podnet_a_enabled is False and podnet_b_enabled is True:
        enabled = podnet_b
        disabled = podnet_a
    elif podnet_a_enabled is True and podnet_b_enabled is True:
        return False, messages[3016]
    elif podnet_a_enabled is False and podnet_b_enabled is False:
        return False, messages[3017]
    else:
        return False, messages[3018]

    try:
      jenv = jinja2.Environment(loader=jinja2.FileSystemLoader(
          os.path.join(template_path))
      )
      template = jenv.get_template("nginx.conf.j2")

      nginx_conf = template.render(
          namespace=namespace
      )
    except Exception as e:
      return False, messages[3020]

    create_configpayload = "\n".join([
        f'tee {nginx_conf_path}<<EOF',
        nginx_conf,
        "EOF"
        ])

    launch_ngixn_payload = "\n".join([
        f'tee {domain_path} metadata <<EOF',
        metadata_json,
        "EOF"
        ])

    # call rcc comms_ssh on enabled PodNet
    try:
        create_metadata, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=create_metadata_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3021]

    if create_metadata.exit_code != SUCCESS_CODE:
        return False, messages[3022] + f'{create_metadata.exit_code}s.'

    # call rcc comms_ssh on enabled PodNet
    try:
        create_userdata, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=create_userdata_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3023]

    if create_userdata.exit_code != SUCCESS_CODE:
        return False, messages[3024]  + f'{create_userdata.exit_code}s.'

    # call rcc comms_ssh on disabled PodNet
    try:
        create_metadata, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=create_metadata_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3031]

    if create_metadata.exit_code != SUCCESS_CODE:
        return False, messages[3032] + f'{create_metadata.exit_code}s.'

    # call rcc comms_ssh on disabled PodNet
    try:
        create_userdata, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=create_userdata_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3033]

    if create_userdata.exit_code != SUCCESS_CODE:
        return False, messages[3034]  + f'{create_userdata.exit_code}s.'


    return True, messages[1000]


def scrub(
        domain_path: str,
) -> Tuple[bool, str]:
    """
    description:
        Removes cloud-init user data and meta data files for a virtual machine on PodNet HA.

    parameters:
        domain_path:
            description: path to the virtual machine's cloud-init directory.
                         This must be the full path, up to and including the
                         version component.
            type: string
            required: true
        config_file:
            description: path to the config.json file
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating if the scrub was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1100: f'1100: Successfully removed {domain_path}/, {domain_path}/metadata and {domain_path}/userdata on both PodNet nodes.',
        2111: f'2111: Config file {config_file} loaded.',
        3111: f'3111: Failed to load config file {config_file}, It does not exist.',
        3112: f'3112: Failed to get `ipv6_subnet` from config file {config_file}',
        3113: f'3113: Invalid value for `ipv6_subnet` from config file {config_file}',
        3114: f'3114: Failed to get `podnet_a_enabled` from config file {config_file}',
        3115: f'3115: Failed to get `podnet_b_enabled` from config file {config_file}',
        3116: f'3116: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3117: f'3117: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3118: f'3118: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3121: f'3121: Failed to connect to the enabled PodNet from the config file {config_file} for remove_metadata payload',
        3122: f'3122: Failed to create metadata file {domain_path}/metadata on the enabled PodNet. Payload exited with status ',
        3123: f'3123: Failed to connect to the enabled PodNet from the config file {config_file} for remove_userdata payload',
        3123: f'3124: Failed to create userdata file {domain_path}/userdata on the enabled PodNet Payload exited with status ',
        3131: f'3131: Successfully removed `metadata` and `userdata` in {domain_path}/ on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file}',
        3132: f'3132: Successfully removed `metadata` and `userdata` in {domain_path}/ on enabled PodNet but failed to create on the disabled PodNet. '
               'Payload exited with status ',
        3133: f'3133: Successfully removed `metadata` and `userdata` in {domain_path}/ on enabled PodNet but failed to connect to the disabled PodNet. '
              f'from the config file {config_file}',
        3134: f'3134: Successfully removed `metadata` and `userdata` in {domain_path}/ on enabled PodNet but failed to create on the disabled PodNet. '
               'Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/etc/cloudcix/pod/configs/config.json'

    # Get load config from config_file
    if not Path(config_file).exists():
        return False, messages[3111]
    with Path(config_file).open('r') as file:
        config = json.load(file)

    # Get the ipv6_subnet from config_file
    ipv6_subnet = config.get('ipv6_subnet', None)
    if ipv6_subnet is None:
        return False, messages[3112]
    # Verify the ipv6_subnet value
    try:
        ipaddress.ip_network(ipv6_subnet)
    except ValueError:
        return False, messages[3113]

    # Get the PodNet Mgmt ips from ipv6_subnet
    podnet_a = f'{ipv6_subnet.split("/")[0]}10:0:2'
    podnet_b = f'{ipv6_subnet.split("/")[0]}10:0:3'

    # Get `podnet_a_enabled` and `podnet_b_enabled`
    podnet_a_enabled = config.get('podnet_a_enabled', None)
    if podnet_a_enabled is None:
        return False, messages[3114]
    podnet_b_enabled = config.get('podnet_b_enabled', None)
    if podnet_a_enabled is None:
        return False, messages[3115]

    # First run on enabled PodNet
    if podnet_a_enabled is True and podnet_b_enabled is False:
        enabled = podnet_a
        disabled = podnet_b
    elif podnet_a_enabled is False and podnet_b_enabled is True:
        enabled = podnet_b
        disabled = podnet_a
    elif podnet_a_enabled is True and podnet_b_enabled is True:
        return False, messages[3116]
    elif podnet_a_enabled is False and podnet_b_enabled is False:
        return False, messages[3117]
    else:
        return False, messages[3118]

    # define payloads
    remove_userdata_payload = f'rm -f {domain_path}/userdata'
    remove_metadata_payload = f'rm -f {domain_path}/metadata'

    # call rcc comms_ssh for metadata removal on enabled PodNet
    try:
        remove_metadata, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=remove_metadata_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3121]

    if remove_metadata.exit_code != SUCCESS_CODE:
        return False, messages[3122] + f'{remove_metadata.exit_code}s.'

    # call rcc comms_ssh for userdata removal on enabled PodNet
    try:
        remove_userdata, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=remove_userdata_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3123]

    if remove_userdata.exit_code != SUCCESS_CODE:
        return False, messages[3124]  + f'{remove_userdata.exit_code}s.'

    # call rcc comms_ssh for metadata removal on disabled PodNet
    try:
        remove_metadata, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=remove_metadata_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3131]

    if remove_metadata.exit_code != SUCCESS_CODE:
        return False, messages[3132] + f'{remove_metadata.exit_code}s.'

    # call rcc comms_ssh for userdata removal on disabled PodNet
    try:
        remove_userdata, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=remove_userdata_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3133]

    if remove_userdata.exit_code != SUCCESS_CODE:
        return False, messages[3134]  + f'{remove_userdata.exit_code}s.'


    return True, messages[1100]

def read(
        domain_path: str,
) -> Tuple[bool, dict, str]:
    """
    description:
        Reads cloud-init user data and meta data files for a virtual machine on
        PodNet HA (if any) and returns them.

    parameters:
        domain_path:
            description: path to the virtual machine's cloud-init directory.
                         This must be the full path, up to and including the
                         version component.
            type: string
            required: true
        config_file:
            description: path to the config.json file
            type: string
            required: false
    return:
        description: |
            A list with 3 items: (1) a boolean status flag indicating if the
            read was successfull, (2) a dict containing the data as read from
            the both machines' current state and (3) the output or success message.
        type: tuple
        items:
          read:
            description: True if all read operations were successful, False otherwise.
            type: boolean
          data:
            type: object
            description: |
              file contents retrieved from both podnet nodes. May be None if nothing
              could be retrieved.
            properties:
              <podnet_ip>:
                description: dict structure holding user data from machine <podnet_ip>
                  type: object
                  userdata:
                    description: |
                      The contents of the `userdata` file at domain_path. May be
                      None upon any read errors.
                    type: string
                  metadata:
                    type: string
                    description: |
                      The contents of the `metadata` file at domain_path. May be
                      None upon any read errors.
    """

    # Define message
    messages = {
        1200: f'1200: Successfully retrieved {domain_path}/, {domain_path}/metadata and {domain_path}/userdata from both PodNet nodes.',
        2211: f'2211: Config file {config_file} loaded.',
        3211: f'3211: Failed to load config file {config_file}, It does not exist.',
        3212: f'3212: Failed to get `ipv6_subnet` from config file {config_file}',
        3213: f'3213: Invalid value for `ipv6_subnet` from config file {config_file}',
        3214: f'3214: Failed to get `podnet_a_enabled` from config file {config_file}',
        3215: f'3215: Failed to get `podnet_b_enabled` from config file {config_file}',
        3216: f'3216: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3217: f'3217: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3218: f'3218: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3221: f'3221: Failed to connect to the enabled PodNet from the config file {config_file} for read_metadata payload',
        3222: f'3222: Failed to read metadata file {domain_path}/metadata on the enabled PodNet. Payload exited with status ',
        3223: f'3223: Failed to connect to the enabled PodNet from the config file {config_file} for read_userdata payload',
        3223: f'3224: Failed to read userdata file {domain_path}/userdata on the enabled PodNet Payload exited with status ',
        3231: f'3231: Successfully read `metadata` and `userdata` from {domain_path}/ on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file}',
        3232: f'3232: Successfully read `metadata` and `userdata` from {domain_path}/ on enabled PodNet but failed to read on the disabled PodNet. '
               'Payload exited with status ',
        3233: f'3233: Successfully read `metadata` and `userdata` from {domain_path}/ on enabled PodNet but failed to connect to the disabled PodNet. '
              f'from the config file {config_file}',
        3234: f'3234: Successfully read `metadata` and `userdata` from {domain_path}/ on enabled PodNet but failed to read on the disabled PodNet. '
               'Payload exited with status ',
    }

    data_dict = None

    # Default config_file if it is None
    if config_file is None:
        config_file = '/etc/cloudcix/pod/configs/config.json'

    # Get load config from config_file
    if not Path(config_file).exists():
        return False, data_dict, messages[3211]
    with Path(config_file).open('r') as file:
        config = json.load(file)

    # Get the ipv6_subnet from config_file
    ipv6_subnet = config.get('ipv6_subnet', None)
    if ipv6_subnet is None:
        return False, data_dict, messages[3212]
    # Verify the ipv6_subnet value
    try:
        ipaddress.ip_network(ipv6_subnet)
    except ValueError:
        return False, data_dict, messages[3213]

    # Get the PodNet Mgmt ips from ipv6_subnet
    podnet_a = f'{ipv6_subnet.split("/")[0]}10:0:2'
    podnet_b = f'{ipv6_subnet.split("/")[0]}10:0:3'

    data_dict = {}

    data_dict[podnet_a] = {
        'userdata': None,
        'metadata': None,
    }

    data_dict[podnet_b] = {
        'userdata': None,
        'metadata': None,
    }

    # Get `podnet_a_enabled` and `podnet_b_enabled`
    podnet_a_enabled = config.get('podnet_a_enabled', None)
    if podnet_a_enabled is None:
        return False, data_dict, messages[3214]
    podnet_b_enabled = config.get('podnet_b_enabled', None)
    if podnet_a_enabled is None:
        return False, data_dict, messages[3215]

    # First run on enabled PodNet
    if podnet_a_enabled is True and podnet_b_enabled is False:
        enabled = podnet_a
        disabled = podnet_b
    elif podnet_a_enabled is False and podnet_b_enabled is True:
        enabled = podnet_b
        disabled = podnet_a
    elif podnet_a_enabled is True and podnet_b_enabled is True:
        return False, data_dict, messages[3216]
    elif podnet_a_enabled is False and podnet_b_enabled is False:
        return False, data_dict, messages[3217]
    else:
        return False, data_dict, messages[3218]

    # define payloads
    read_userdata_payload = f'cat {domain_path}/userdata'
    read_metadata_payload = f'cat {domain_path}/metadata'

    # call rcc comms_ssh for metadata retrieval from enabled PodNet
    try:
        read_metadata, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=read_metadata_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, data_dict, messages[3221]

    if read_metadata.exit_code != SUCCESS_CODE:
        return False, data_dict, messages[3222] + f'{read_metadata.exit_code}s.'

    data_dict[enabled]['metadata'] = stdout

    # call rcc comms_ssh for userdata retrieval from enabled PodNet
    try:
        read_userdata, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=read_userdata_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, data_dict, messages[3223]

    if read_userdata.exit_code != SUCCESS_CODE:
        return False, data_dict, messages[3224]  + f'{read_userdata.exit_code}s.'

    data_dict[enabled]['userdata'] = stdout

    # call rcc comms_ssh for metadata retrieval from disabled PodNet
    try:
        read_metadata, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=read_metadata_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, data_dict, messages[3231]

    if read_metadata.exit_code != SUCCESS_CODE:
        return False, data_dict, messages[3232] + f'{read_metadata.exit_code}s.'

    data_dict[enabled]['metadata'] = stdout

    # call rcc comms_ssh for userdata retrieval from disabled PodNet
    try:
        read_userdata, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=read_userdata_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, data_dict, messages[3233]

    if read_userdata.exit_code != SUCCESS_CODE:
        return False, data_dict, messages[3234]  + f'{read_userdata.exit_code}s.'

    data_dict[enabled]['userdata'] = stdout

    return True, data_dict, messages[1200]
