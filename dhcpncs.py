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
        namespace: str,
        dhcp_ranges: list,
        dhcp_hosts: list,
        config_file=None,
) -> Tuple[bool, str]:
    """
    description:
        Configures and starts a dnsmasq instance to act as DHCP server inside a VRF network name space on a PodNet node.

    parameters:
        namespace:
            description: VRF network name space's identifier, such as 'VRF453
            type: string
            required: true
        dhcp_ranges:
          type: array
        dhcp_hosts:
          type: array
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

    dnsmasq_config_path = '/etc/netns/{namespace}/dnsmasq.conf'
    dnsmasq_hosts_path = '/etc/netns/{namespace}/dnsmasq-hosts.conf'
    pidfile= '/run/dnsmasq-{namespace}s.pid'

    # Define message
    messages = {
        1000: f'1000: Successfully created {dnsmasq_config_path} and started dnsmasq process on both PodNet nodes.',
        2011: f'2011: Config file {config_file} loaded.',
        3011: f'3011: Failed to load config file {config_file}, It does not exist.',
        3012: f'3012: Failed to get `ipv6_subnet` from config file {config_file}',
        3013: f'3013: Invalid value for `ipv6_subnet` from config file {config_file}',
        3014: f'3014: Failed to get `podnet_a_enabled` from config file {config_file}',
        3015: f'3015: Failed to get `podnet_b_enabled` from config file {config_file}',
        3016: f'3016: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3017: f'3017: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3018: f'3018: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3019: f'3019: Failed to render jinja2 template for {dnsmasq_conf_path}',
        3020: f'3020: Failed to connect to the enabled PodNet from the config file {config_file} for find_process_payload',
        3021: f'3021: Failed to run find_process_payload on the enabled PodNet. Payload exited with status ',
        3022: f'3022: Failed to connect to the enabled PodNet from the config file {config_file} for create_config_payload',
        3023: f'3023: Failed to create config file {dnsmasq_config_path} on the enabled PodNet. Payload exited with status ',
        3024: f'3024: Failed to connect to the enabled PodNet from the config file {config_file} for reload_dnsmasq_payload',
        3025: f'3025: Failed to run reload_dnsmasq_payload on the enabled PodNet. Payload exited with status ',
        3026: f'3026: Failed to connect to the enabled PodNet from the config file {config_file} for start_dnsmasq_payload',
        3027: f'3027: Failed to start dnsmasq on the enabled PodNet. Payload exited with status ',
        3030: f'3030: Failed to connect to the enabled PodNet from the config file {config_file} for find_process_payload',
        3031: f'3031: Failed to run find_process_payload on the disabled PodNet. Payload exited with status ',
        3032: f'3032: Successfully created {dnsmasq_config_path} and started dnsmasq on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for create_config_payload.',
        3033: f'3033: Successfully created {dnsmasq_config_path} and started dnsmasq on enabled PodNet but failed to create {dnsmasq_config_path} on the disabled PodNet. '
               'Payload exited with status ',
        3034: f'3034: Failed to connect to the disabled PodNet from the config file {config_file} for reload_dnsmasq_payload',
        3035: f'3035: Failed to run reload_dnsmasq_payload on the disabled PodNet. Payload exited with status ',
        3036: f'3036: Successfully created {dnsmasq_config_path} on both PodNet nodes and started dnsmasq on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for start_dnsmasq_payload.',
        3037: f'3037: Successfully created {dnsmasq_config_path} on both PodNet nodes and started dnsmasq on enabled PodNet but failed to start dnsmasq on the disabled PodNet. '
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
      template = jenv.get_template("dnsmasq.conf.j2")

      dnsmasq_conf = template.render(
          hostsfile=dnsmasq_hosts_path,
          pidfile=pidfile,
          ranges=dhcp_ranges
      )
    except Exception as e:
      return False, messages[3019]

    try:
      jenv = jinja2.Environment(loader=jinja2.FileSystemLoader(
          os.path.join(template_path))
      )
      template = jenv.get_template("dnsmasq.hosts.j2")

      dnsmasq_hosts = template.render(
          hosts=dhcp_hosts,
      )
    except Exception as e:
      return False, messages[3020]

    create_config_payload = "\n".join([
        f'tee {dnsmasq_config_path}s <<EOF',
        dnsmasq_conf,
        "EOF"
        ])

    create_hosts_payload = "\n".join([
        f'tee {dnsmasq_hosts_path}s <<EOF',
        dnsmasq_hosts,
        "EOF"
        ])

    # We need to check for existing process and SIGHUP its PID if one exist:
    find_process_payload = "ps auxw | grep dnsmasq | grep {dnsmasq_config_path}s | awk '{print $2}'"
    start_dnsmasq_payload = f'ip netns exec {namespace} dnsmasq --config {dnsmasq_conf_path}s'

    # call rcc comms_ssh on enabled PodNet to find existing process
    try:
        existing_process, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=find_process_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3021]

    reload_dnsmasq_payload = None
    if (existing_process.exit_code == SUCCESS_CODE) and (stdout != ""):
        reload_dnsmasq_payload = f'kill -HUP {stdout}s'
    else:
       return False, messages[3022] + f'{existing_process.exit_code}s.'

    # call rcc comms_ssh on enabled PodNet to create config
    try:
        create_config, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=create_config_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3023]

    if create_config.exit_code != SUCCESS_CODE:
        return False, messages[3024] + f'{create_config.exit_code}s.'

    # call rcc comms_ssh on enabled PodNet to create config
    try:
        create_hosts, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=create_hosts_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3025]

    if create_hosts.exit_code != SUCCESS_CODE:
        return False, messages[3026] + f'{create_hosts.exit_code}s.'

    if reload_dnsmasq_payload is not None:
        # call rcc comms_ssh on enabled PodNet to SIGHUP existing process
        try:
            start_dnsmasq, stdout, stderr = comms_ssh(
                host_ip=enabled,
                payload=reload_dnsmasq_payload,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[3027]

        if start_dnsmasq.exit_code != SUCCESS_CODE:
            return False, messages[3028]  + f'{start_dnsmasq.exit_code}s.'
    else:
        # call rcc comms_ssh on enabled PodNet
        try:
            start_dnsmasq, stdout, stderr = comms_ssh(
                host_ip=enabled,
                payload=start_dnsmasq_payload,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[3029]

        if start_dnsmasq.exit_code != SUCCESS_CODE:
            return False, messages[3030]  + f'{start_dnsmasq.exit_code}s.'

    # call rcc comms_ssh on disabled PodNet to find existing process
    try:
        existing_process, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=find_process_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3041]

    reload_dnsmasq_payload = None
    if (existing_process.exit_code == SUCCESS_CODE) and (stdout != ""):
        reload_dnsmasq_payload = f'kill -HUP {stdout}s'
    else:
       return False, messages[3042] + f'{existing_process.exit_code}s.'

    # call rcc comms_ssh on disabled PodNet to create config
    try:
        create_config, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=create_config_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3043]

    if create_config.exit_code != SUCCESS_CODE:
        return False, messages[3044] + f'{create_config.exit_code}s.'

    # call rcc comms_ssh on disabled PodNet to create config
    try:
        create_hosts, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=create_hosts_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3045]

    if create_hosts.exit_code != SUCCESS_CODE:
        return False, messages[3046] + f'{create_hosts.exit_code}s.'

    if reload_dnsmasq_payload is not None:
        # call rcc comms_ssh on disabled PodNet to SIGHUP existing process
        try:
            start_dnsmasq, stdout, stderr = comms_ssh(
                host_ip=disabled,
                payload=reload_dnsmasq_payload,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[3047]

        if start_dnsmasq.exit_code != SUCCESS_CODE:
            return False, messages[3048]  + f'{start_dnsmasq.exit_code}s.'
    else:
        # call rcc comms_ssh on disabled PodNet
        try:
            start_dnsmasq, stdout, stderr = comms_ssh(
                host_ip=disabled,
                payload=start_dnsmasq_payload,
                username='robot',
            )
        except CouldNotConnectException:
            return False, messages[3049]

        if start_dnsmasq.exit_code != SUCCESS_CODE:
            return False, messages[3050]  + f'{start_dnsmasq.exit_code}s.'

    return True, messages[1000]


def scrub(
        namespace: str,
) -> Tuple[bool, str]:
    """
    description: |
        Stops a dnsmasq instance that acts as a DHCP server inside a VRF
        network name space on a PodNet node and removes its configuration.

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

    dnsmasq_config_path = '/etc/netns/{namespace}/dnsmasq.conf'
    dnsmasq_hosts_path = '/etc/netns/{namespace}/dnsmasq-hosts.conf'
    pidfile= '/run/dnsmasq-{namespace}s.pid'

    # Define message
    messages = {
        1100: f'1100: Successfully stopped dnsmasq process and deleted {dnsmasq_config_path}s, {dnsmasq_hosts_path}s.',
        2111: f'2111: Config file {config_file} loaded.',
        3111: f'3111: Failed to load config file {config_file}, It does not exist.',
        3112: f'3112: Failed to get `ipv6_subnet` from config file {config_file}',
        3113: f'3113: Invalid value for `ipv6_subnet` from config file {config_file}',
        3114: f'3114: Failed to get `podnet_a_enabled` from config file {config_file}',
        3115: f'3115: Failed to get `podnet_b_enabled` from config file {config_file}',
        3116: f'3116: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3117: f'3117: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3118: f'3118: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3121: f'3123: Failed to connect to the enabled PodNet from the config file {config_file} for start_dnsmasq_payload',
        3122: f'3124: Failed to stop dnsmasq on the enabled PodNet. Payload exited with status ',
        3123: f'3121: Failed to connect to the enabled PodNet from the config file {config_file} for remove_config_payload',
        3124: f'3122: Failed to delete config files {dnsmasq_config_path}s, {dnsmasq_hosts_path}s on the enabled PodNet. Payload exited with status ',
        3131: f'3131: Successfully stopped dnsmasq and deleted {dnsmasq_config_path}, {dnsmasq_hosts_path} on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for stop_dnsmasq_payload.',
        3132: f'3132: Successfully stopped dnsmasq and deleted {dnsmasq_config_path}, {dnsmasq_hosts_path}s on enabled PodNet but failed to stop dnsmasq on the disabled PodNet. '
               'Payload exited with status ',
        3133: f'3133: Successfully stoppend dnsmasq and deleted {dnsmasq_config_path}, {dnsmasq_hosts_path}s on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for remove_config_payload.',
        3134: f'3134: Successfully stopped dnsmasq on both PodNet nodes and deleted {dnsmasq_config_path}s, {dnsmasq_hosts_path} on enabled PodNet but failed to stop dnsmasq on the disabled PodNet. '
               'Payload exited with status ',
    }

    # Default config_file if it is None
    if config_file is None:
        config_file = '/etc/cloudcix/pod/configs/config.json'

    # Load config from config_file
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
    stop_dnsmasq_payload = f'kill $(cat {pidfile}s)'
    delete_config_payload = f'rm -f {dnsmasq_config_path}s {dnsmasq_hosts_path}s'

    # call rcc comms_ssh for stopping dnsmasq on enabled PodNet
    try:
        stop_dnsmasq, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=stop_dnsmasq_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3121]

    if stop_dnsmasq.exit_code != SUCCESS_CODE:
        return False, messages[3122] + f'{stop_dnsmasq.exit_code}s.'

    # call rcc comms_ssh for dnsmasq config file removal on enabled PodNet
    try:
        remove_config, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=remove_config_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3123]

    if remove_config.exit_code != SUCCESS_CODE:
        return False, messages[3124]  + f'{remove_config.exit_code}s.'

    # call rcc comms_ssh for stopping dnsmasq on disabled PodNet
    try:
        stop_dnsmasq, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=stop_dnsmasq_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3131]

    if stop_dnsmasq.exit_code != SUCCESS_CODE:
        return False, messages[3132] + f'{stop_dnsmasq.exit_code}s.'

    # call rcc comms_ssh for dnsmasq config file removal on disabled PodNet
    try:
        remove_config, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=remove_config_payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3133]

    if remove_config.exit_code != SUCCESS_CODE:
        return False, messages[3134]  + f'{remove_config.exit_code}s.'


    return True, messages[1100]

def read(
        namespace: str,
        config_file=None
) -> Tuple[bool, dict, str]:
    """
    description:
        Checks configuration file and process status of dnsmasq process providing DHCP from a VRF namespace on the PodNet node.

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
        items:
          read:
            description: True if all read operations were successful, False otherwise.
            type: boolean
          data:
            type: object
            description: |
              process status and file contents retrieved from both podnet nodes. May be None if nothing
              could be retrieved.
            properties:
              <podnet_ip>:
                description: structure holding process status/config file contents from machine <podnet_ip>
                type: object
                  process_status:
                  type: string
                    description: |
                      The contents of the `userdata` file at domain_path. May be
                      None upon any read errors.
                    type: string
                  config_file:
                    type: string
                    description: |
                      The contents of the `metadata` file at domain_path. May be
                      None upon any read errors.
          errors:
            type: array
            description: List of success/error messages produced while reading state
            items:
              type: string
    """

    dnsmasq_config_path = '/etc/netns/{namespace}/dnsmasq.conf'
    dnsmasq_hosts_path = '/etc/netns/{namespace}/dnsmasq-hosts.conf'
    pidfile= '/run/nginx-{namespace}s.pid'

    # Define message
    messages = {
        1200: f'1200: Successfully retrieved dnsmasq process status and {dnsmasq_config_path}s, {dnsmasq_hosts_path}s from both PodNet nodes.',
        2211: f'2211: Config file {config_file} loaded.',
        3211: f'3211: Failed to load config file {config_file}, It does not exist.',
        3212: f'3212: Failed to get `ipv6_subnet` from config file {config_file}',
        3213: f'3213: Invalid value for `ipv6_subnet` from config file {config_file}',
        3214: f'3214: Failed to get `podnet_a_enabled` from config file {config_file}',
        3215: f'3215: Failed to get `podnet_b_enabled` from config file {config_file}',
        3216: f'3216: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are True',
        3217: f'3217: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, both are False',
        3218: f'3218: Invalid values for `podnet_a_enabled` and `podnet_b_enabled`, one or both are non booleans',
        3221: f'3221: Failed to connect to the enabled PodNet from the config file {config_file} for read_config_payload',
        3222: f'3222: Failed to read config file {dnsmasq_config_path}s on the enabled PodNet. Payload exited with status ',
        3223: f'3223: Failed to connect to the enabled PodNet from the config file {config_file} for find_process_payload',
        3223: f'3224: Failed to execute find_process_payload on the enabled PodNet node. Payload exited with status ',
        3231: f'3231: Successfully retrieved dnsmasq process status and {dnsmasq_config_path}s from enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for read_config_payload',
        3232: f'3232: Successfully retrieved dnsmasq process status and {dnsmasq_config_path}s from enabled PodNet but failed to execute read_config_payload '
               'on the disabled PodNet. Payload exited with status ',
        3233: f'3233: Successfully retrieved {dnsmasq_config_file}s from both PodNet nodes but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for find_process_payload.',
        3234: f'3234: Successfully retrieved {dnsmasq_config_file}s from both PodNet nodes but failed to execute find_process_payload on the disabled PodNet. '
               'Payload exited with status ',
    }

    retval = True
    data_dict = None
    message_list = ()

    # Default config_file if it is None
    if config_file is None:
        config_file = '/etc/cloudcix/pod/configs/config.json'

    # Get load config from config_file
    if not Path(config_file).exists():
        retval = False
        message_list.append(messages[3211])
    with Path(config_file).open('r') as file:
        config = json.load(file)

    # Get the ipv6_subnet from config_file
    ipv6_subnet = config.get('ipv6_subnet', None)
    if ipv6_subnet is None:
        retval = False
        message_list.append(messages[3212])
    # Verify the ipv6_subnet value
    try:
        ipaddress.ip_network(ipv6_subnet)
    except ValueError:
        retval = False
        message_list.append(messages[3213])

    # Get the PodNet Mgmt ips from ipv6_subnet
    podnet_a = f'{ipv6_subnet.split("/")[0]}10:0:2'
    podnet_b = f'{ipv6_subnet.split("/")[0]}10:0:3'

    data_dict = {}

    data_dict[podnet_a] = {
        'process_status': None,
        'config_file': None,
    }

    data_dict[podnet_b] = {
        'process_status': None,
        'config_file': None,
    }

    # Get `podnet_a_enabled` and `podnet_b_enabled`
    podnet_a_enabled = config.get('podnet_a_enabled', None)
    if podnet_a_enabled is None:
        retval = False
        message_list.append(messages[3214])
    podnet_b_enabled = config.get('podnet_b_enabled', None)
    if podnet_a_enabled is None:
        retval = False
        message_list.append(messages[3215])

    # First run on enabled PodNet
    if podnet_a_enabled is True and podnet_b_enabled is False:
        enabled = podnet_a
        disabled = podnet_b
    elif podnet_a_enabled is False and podnet_b_enabled is True:
        enabled = podnet_b
        disabled = podnet_a
    elif podnet_a_enabled is True and podnet_b_enabled is True:
        retval = False
        message_list.append(messages[3216])
    elif podnet_a_enabled is False and podnet_b_enabled is False:
        retval = False
        message_list.append(messages[3217])
    else:
        retval = False
        message_list.append(messages[3218])

    # define payloads
    read_config_payload = f'cat {dnsmasq_config_path}'
    read_hosts_payload = f'cat {dnsmasq_hosts_path}'
    find_process_payload = f'ps auxw | grep dnsmasq | grep {dnsmasq_config_path}s'

    # call rcc comms_ssh for config retrieval from enabled PodNet
    try:
        read_config, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=read_config_payload,
            username='robot',
        )
    except CouldNotConnectException:
        retval = False
        message_list.append(messages[3221])

    if read_config.exit_code != SUCCESS_CODE:
        retval = False
        message_list.append(messages[3222] + f'{read_config.exit_code}s.')

    data_dict[enabled]['config_file'] = stdout

    # call rcc comms_ssh for process_status retrieval from enabled PodNet
    try:
        read_process_status, stdout, stderr = comms_ssh(
            host_ip=enabled,
            payload=find_process_payload,
            username='robot',
        )
    except CouldNotConnectException:
        retval = False
        message_list.append(messages[3223])

    if read_process_status.exit_code != SUCCESS_CODE:
        retval = False
        message_list.append(messages[3224]  + f'{read_process_status.exit_code}s.')

    data_dict[enabled]['process_status'] = stdout

    # call rcc comms_ssh for config retrieval from disabled PodNet
    try:
        read_config, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=read_config_payload,
            username='robot',
        )
    except CouldNotConnectException:
        retval = False
        message_list.append(messages[3231])

    if read_config.exit_code != SUCCESS_CODE:
        retval = False
        message_list.append(messages[3232] + f'{read_config.exit_code}s.')

    data_dict[enabled]['config_file'] = stdout

    # call rcc comms_ssh for process_status retrieval from disabled PodNet
    try:
        read_process_status, stdout, stderr = comms_ssh(
            host_ip=disabled,
            payload=find_process_payload,
            username='robot',
        )
    except CouldNotConnectException:
        retval = False
        message_list.append(messages[3233])

    if read_process_status.exit_code != SUCCESS_CODE:
        retval = False
        message_list.append(messages[3234]  + f'{read_process_status.exit_code}s.')

    data_dict[enabled]['process_status'] = stdout

    return retval, data_dict, messages[1200]
