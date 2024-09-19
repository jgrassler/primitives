"""
Primitive to Build, Read and Scrub cloud-init userdata/metadata payloads on PodNet HA
"""

# stdlib
import json
import ipaddress
from pathlib import Path
from typing import Tuple
# lib
from cloudcix.rcc import comms_ssh, CHANNEL_SUCCESS, VALIDATION_ERROR, CONNECTION_ERROR
from cloudcix_primitives.utils import load_pod_config, SSHCommsWrapper, PodnetErrorFormatter
# local


__all__ = [
    'build',
    'scrub',
    'read',
]

SUCCESS_CODE = 0


def build(
        domain_path: str,
        metadata: dict,
        userdata: str,
        config_file=None,
) -> Tuple[bool, str]:
    """
    description:
        Creates cloud-init user data and meta data files for a virtual machine on PodNet HA.

    parameters:
        domain_path:
            description: | path to the virtual machine's cloud-init directory.
                           This must be the full path, up to and including the
                           metaddata version component.
            type: string
            required: true
        metadata:
          description: data structure that contains the machine's metadata
          type: object
          required: true
          properties:
            instance_id:
              type: string
              required: true
              description: | libvirt domain name for VM. Typically composed from
                             numerical project ID and VM ID as follows:
                             `<project_id>_<domain_id>`.
            network:
              type: object
              required: true
              description: |
                  the VM's network configuration. This is a dictionary representing a netplan v2
                  configuration. Such a dictionary can be obtained by
                  deserializing a netplan v2 configuration file using a YAML
                  parser.
        config_file:
            description: path to the config.json file
            type: string
            required: false
        userdata:
            description: the cloud-init user data payload to pass into the virtual machine
            type: string
            required: true
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'1000: Successfully created {domain_path}/metadata and {domain_path}/userdata on both PodNet nodes.',
        3021: f'3021: Failed to connect to the enabled PodNet from config file {config_file} for create_metadata payload: ',
        3022: f'3022: Failed to run create_metadata payload on the enabled PodNet. Payload exited with status ',
        3023: f'3023: Failed to connect to the enabled PodNet from config file {config_file} for create_userdata payload: ',
        3024: f'3024: Failed to run create_userdata payload on the enabled PodNet. Payload exited with status ',

        3031: f'3021: Failed to connect to the enabled PodNet from config file {config_file} for create_metadata payload: ',
        3032: f'3022: Failed to run create_metadata payload on the enabled PodNet. Payload exited with status ',
        3033: f'3023: Failed to connect to the enabled PodNet from config file {config_file} for create_userdata payload: ',
        3034: f'3024: Failed to run create_userdata payload on the enabled PodNet. Payload exited with status ',
    }

    metadata_json = json.dumps(
        metadata,
        indent=1,
        sort_keys=True,
    )

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    status, config_data, msg = load_pod_config(config_file)
    if not status:
      if config_data['raw'] is None:
          return False, msg
      else:
          return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
              indent=2,
              sort_keys=True)
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['disabled']


    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        payloads = {
            'create_metadata': "\n".join([
                f'tee {domain_path}/metadata <<EOF',
                metadata_json,
                "EOF"
            ]),

            'create_userdata': "\n".join([
                    f'tee {domain_path}/userdata <<EOF',
                    userdata,
                    "EOF"
                    ])
        }


        ret = rcc.run(payloads['create_metadata'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        fmt.add_successful('create_metadata', ret)

        ret = rcc.run(payloads['create_userdata'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        fmt.add_successful('create_userdata', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled, 3020, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3030, successful_payloads)
    if status == False:
        return status, msg

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
        3121: f'3121: Failed to connect to the enabled PodNet from the config file {config_file} for remove_metadata payload: ',
        3122: f'3122: Failed to create metadata file {domain_path}/metadata on the enabled PodNet. Payload exited with status ',
        3123: f'3123: Failed to connect to the enabled PodNet from the config file {config_file} for remove_userdata payload: ',
        3123: f'3124: Failed to create userdata file {domain_path}/userdata on the enabled PodNet Payload exited with status ',
        3131: f'3131: Successfully removed `metadata` and `userdata` in {domain_path}/ on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file}: ',
        3132: f'3132: Successfully removed `metadata` and `userdata` in {domain_path}/ on enabled PodNet but failed to create on the disabled PodNet. '
               'Payload exited with status ',
        3133: f'3133: Successfully removed `metadata` and `userdata` in {domain_path}/ on enabled PodNet but failed to connect to the disabled PodNet. '
              f'from the config file {config_file}: ',
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
    ret = comms_ssh(
        host_ip=enabled,
        payload=remove_metadata_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3121] + f'channel_code: {ret["channel_code"]}.\nchannel_message: {channel_message}\nchannel_error: {channel_error}'

    if ret["payload_code"] != SUCCESS_CODE:
        return False, messages[3122] + f'{ret["payload_code"]}.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh for userdata removal on enabled PodNet
    ret = comms_ssh(
        host_ip=enabled,
        payload=remove_userdata_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3123] + f'channel_code: {ret["channel_code"]}.\nchannel_message: {channel_message}\nchannel_error: {channel_error}'

    if ret["payload_code"] != SUCCESS_CODE:
        return False, messages[3124]  + f'{ret["payload_code"]}.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh for metadata removal on disabled PodNet
    ret = comms_ssh(
        host_ip=disabled,
        payload=remove_metadata_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3131] + f'channel_code: {ret["channel_code"]}.\nchannel_message: {channel_message}\nchannel_error: {channel_error}'

    if ret["payload_code"] != SUCCESS_CODE:
        return False, messages[3132] + f'{ret["payload_code"]}.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh for userdata removal on disabled PodNet
    ret = comms_ssh(
        host_ip=disabled,
        payload=remove_userdata_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3133] + f'channel_code: {ret["channel_code"]}.\nchannel_message: {channel_message}\nchannel_error: {channel_error}'

    if ret["payload_code"] != SUCCESS_CODE:
        return False, messages[3134]  + f'{ret["payload_code"]}.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'


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
        3221: f'3221: Failed to connect to the enabled PodNet from the config file {config_file} for read_metadata payload: ',
        3222: f'3222: Failed to read metadata file {domain_path}/metadata on the enabled PodNet. Payload exited with status ',
        3223: f'3223: Failed to connect to the enabled PodNet from the config file {config_file} for read_userdata payload: ',
        3223: f'3224: Failed to read userdata file {domain_path}/userdata on the enabled PodNet Payload exited with status ',
        3231: f'3231: Successfully read `metadata` and `userdata` from {domain_path}/ on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file}: ',
        3232: f'3232: Successfully read `metadata` and `userdata` from {domain_path}/ on enabled PodNet but failed to read on the disabled PodNet. '
               'Payload exited with status ',
        3233: f'3233: Successfully read `metadata` and `userdata` from {domain_path}/ on enabled PodNet but failed to connect to the disabled PodNet. '
              f'from the config file {config_file}: ',
        3234: f'3234: Successfully read `metadata` and `userdata` from {domain_path}/ on enabled PodNet but failed to read on the disabled PodNet. '
               'Payload exited with status ',
    }

    retval = True
    data_dict = {}
    message_list = ()

    # Default config_file if it is None
    if config_file is None:
        config_file = '/etc/cloudcix/pod/configs/config.json'

    # Get load config from config_file
    if not Path(config_file).exists():
        retval = False
        message_list.append(messages[3211])
        # Config file not found, cannot proceed
        return retval, data_dict, message_list

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
        message_list.append(messages[3218])

    if retval == False:
        return retval, data_dict, message_list

    # define payloads
    read_userdata_payload = f'cat {domain_path}/userdata'
    read_metadata_payload = f'cat {domain_path}/metadata'

    # call rcc comms_ssh for metadata retrieval from enabled PodNet
    ret = comms_ssh(
        host_ip=enabled,
        payload=read_metadata_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        retval = False
        message_list.append(messages[3221] + f'channel_code: {ret["channel_code"]}.\nchannel_message: {channel_message}\nchannel_error: {channel_error}')

    if (ret["payload_code"] != SUCCESS_CODE) and (ret["payload_code"] is not None):
        retval = False
        message_list.append(messages[3222] + f'{ret["payload_code"]}.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}')

    data_dict[enabled]['metadata'] = ret["payload_message"]

    # call rcc comms_ssh for userdata retrieval from enabled PodNet
    ret = comms_ssh(
        host_ip=enabled,
        payload=read_userdata_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        retval = False
        message_list.append(messages[3223] + f'channel_code: {ret["channel_code"]}.\nchannel_message: {channel_message}\nchannel_error: {channel_error}')

    if (ret["payload_code"] != SUCCESS_CODE) and (ret["payload_code"] is not None):
        retval = False
        message_list.append(messages[3224]  + f'{ret["payload_code"]}.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}')

    data_dict[enabled]['userdata'] = ret["payload_message"]

    # call rcc comms_ssh for metadata retrieval from disabled PodNet
    ret = comms_ssh(
        host_ip=disabled,
        payload=read_metadata_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        retval = False
        message_list.append(messages[3231] + f'channel_code: {ret["channel_code"]}.\nchannel_message: {channel_message}\nchannel_error: {channel_error}')

    if (ret["payload_code"] != SUCCESS_CODE) and (ret["payload_code"] is not None):
        retval = False
        message_list.append(messages[3232] + f'{ret["payload_code"]}.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}')

    data_dict[enabled]['metadata'] = ret["payload_message"]

    # call rcc comms_ssh for userdata retrieval from disabled PodNet
    ret = comms_ssh(
        host_ip=disabled,
        payload=read_userdata_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        retval = False
        message_list.append(messages[3233] + f'channel_code: {ret["channel_code"]}.\nchannel_message: {channel_message}\nchannel_error: {channel_error}')

    if (ret["payload_code"] != SUCCESS_CODE) and (ret["payload_code"] is not None):
        retval = False
        message_list.append(messages[3234]  + f'{ret["payload_code"]}.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}')

    data_dict[enabled]['userdata'] = ret["payload_message"]

    message_list.append(messages[1200])
    return retval, data_dict, message_list
