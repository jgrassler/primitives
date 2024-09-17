"""
Primitive to Build, Read and Scrub a network name space on PodNet HA
"""

# stdlib
import json
import ipaddress
from pathlib import Path
from typing import Tuple
# lib
from cloudcix.rcc import comms_ssh, CHANNEL_SUCCESS, VALIDATION_ERROR, CONNECTION_ERROR
from utils import load_pod_config, CommsWrapper, ErrorFormatter
# local


__all__ = [
    'build',
    'scrub',
    'read',
]

SUCCESS_CODE = 0


def build(
        name: str,
        lo_addr='169.254.169.254',
        config_file=None,
) -> Tuple[bool, str]:
    """
    description:
        Creates a network name space on PodNet HA.

    parameters:
        name:
            description: network namespace's name
            type: string
            required: true
        lo_addr:
            description: IP address to assign to the namespace's loopback interface.
            type: string
            required: false
        config_file:
            description: |
                path to the config.json file. Defaults to /opt/robot/config.json if
                not supplied.
            type: string
            required: false
    return:
        description: |
            A tuple with a boolean flag stating if the build was successful or not and
            the output or error message.
        type: tuple
    """

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Define messages

    messages = {
        # Enabled Podnet
        1000: f'1000: Successfully created network name space {name} on both PodNet nodes.',
        1001: f'1001: Success: name space {name} exists already',
        3021: f'3021: Failed to connect to the enabled PodNet from the config file {config_file} for find_namespace payload: ',
        3022: f'3022: Failed to connect to the enabled PodNet from the config file {config_file} for create_namespace payload: ',
        3023: f'3023: Failed to run create_namespace pyaload on the enabled PodNet. Payload exited with status ',
        3024: f'3024: Failed to run enable_forwardv4 payload in name space {name} on the enabled PodNet. Payload exited with status ',
        3025: f'3025: Failed to run enable_forwardv4 payload on enabled PodNet. Payload exited with status ',
        3026: f'3026: Failed to connect to the enabled PodNet from the config file {config_file} for enable_forwardv6 payload: ',
        3027: f'3027: Failed to run enable_forwardv6 payload on the enabled PodNet. Payload exited with status ',
        3028: f'3028: Failed to connect to the enabled PodNet from the config file {config_file} for enable_lo payload: ',
        3029: f'3029: Failed to run enable_lo payload on the enabled PodNet from the config file {config_file}. Payload exited with status ',
        3030: f'3030: Failed to connect to the enabled PodNet from the config file {config_file} for find_lo1 payload: ',
        3031: f'3031: Failed to connect to the enabled PodNet from the config file {config_file} for create_lo1 payload: ',
        3032: f'3032: Failed to run create_lo1 payload on the enabled PodNet from the config file {config_file}. Payload exited with status ',
        3033: f'3033: Failed to connect to the enabled PodNet from the config file {config_file} for find_lo1 payload: ',
        3034: f'3034: Failed to connect to the enabled PodNet from the config file {config_file} for create_lo1_address payload: ',
        3035: f'3035: Failed to run create_lo1_address payload on the enabled PodNet from the config file {config_file}. Payload exited with status ',
        3036: f'3036: Failed to connect to the enabled PodNet from the config file {config_file} for enable_lo1 payload: ',
        3037: f'3037: Failed to run enable_lo1 payload on the enabled PodNet from the config file {config_file}. Payload exited with status ',

        # Disabled Podnet
        3051: f'3051: Failed to connect to the disabled PodNet from the config file {config_file} for find_namespace payload: ',
        3052: f'3052: Failed to connect to the disabled PodNet from the config file {config_file} for create_namespace payload: ',
        3053: f'3053: Failed to run create_namespace payload on the disabled PodNet. Payload exited with status ',
        3054: f'3034: Failed to connect to the disabled PodNet from the config file {config_file} for enable_forwardv4 payload: ',
        3055: f'3055: Failed to run enable_forwardv4 payload on disabled PodNet. Payload exited with status ',
        3056: f'3056: Failed to connect to the disabled PodNet from the config file {config_file} for enable_forwardv6 payload: ',
        3057: f'3057: Failed to run enable_forwardv6 payload on disabled PodNet. Payload exited with status ',
        3058: f'3058: Failed to connect to the disabled PodNet from the config file {config_file} for enable_lo payload: ',
        3059: f'3059: Failed to run enable_lo payload on the disabled PodNet from the config file {config_file}. Payload exited with status ',
        3060: f'3060: Failed to connect to the disabled PodNet from the config file {config_file} for find_lo1 payload: ',
        3061: f'3061: Failed to connect to the disabled PodNet from the config file {config_file} for create_lo1 payload: ',
        3062: f'3062: Failed to run create_lo1 payload on the disabled PodNet from the config file {config_file}. Payload exited with status ',
        3063: f'3063: Failed to connect to the disabled PodNet from the config file {config_file} for find_lo1 payload: ',
        3064: f'3064: Failed to connect to the disabled PodNet from the config file {config_file} for create_lo1_address payload: ',
        3065: f'3065: Failed to run create_lo1_address payload on the disabled PodNet from the config file {config_file}. Payload exited with status ',
        3066: f'3066: Failed to connect to the disabled PodNet from the config file {config_file} for enable_lo1 payload: ',
        3067: f'3067: Failed to run enable_lo1 payload on the disabled PodNet from the config file {config_file}. Payload exited with status ',
    }

    status, config_data, msg = load_pod_config(config_file)
    if not status:
      if config_data['raw'] is None:
          return False, msg
      else:
          return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
              indent=2,
              sort_keys=True)
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['enabled']

    name_grepsafe = name.replace('.', '\.')
    lo_addr_grepsafe = lo_addr.replace('.', '\.')

    def run_podnet(podnet_node, prefix, successful_payloads):
        rcc = CommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = ErrorFormatter(
            messages,
            podnet_node,
            podnet_node == enabled,
            prefix,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'}
        )

        payloads = {
            'find_namespace':     "ip netns list | grep -w '{name_grepsafe}'",
            'create_namespace':   "ip netns create {name}",
            'enable_forwardv4':   "ip netns exec {name} sysctl --write net.ipv4.ip_forward=1",
            'enable_forwardv6':   "ip netns exec {name} sysctl --write net.ipv6.conf.all.forwarding=1",
            'enable_lo':          "ip netns exec {name} ip link set dev lo up",
            'find_lo1':           "ip netns exec {name} ip link show lo1",
            'add_lo1':            "ip netns exec {name} ip link add lo1 type dummy",
            'find_lo1_address':   "ip netns exec {name} show dev lo1 | grep -w '{lo_addr_grepsafe}'",
            'create_lo1_address': "ip netns exec {name} ip addr add {lo_addr} dev lo1",
            'enable_lo1':         "ip netns exec {name} ip link set dev lo1 up",
        }

        ret = rcc.run(payloads['find_namespace'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, prefix+1)
        create_namespace = True
        if ret["payload_code"] == SUCCESS_CODE:
            # No need to create this name space if it exists already
            create_namespace = False
        fmt.add_successful('find_namespace')

        if create_namespace:
            # call rcc comms_ssh on enabled PodNet
            ret = rcc.run(payloads['create_namespace'])

            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, messages[prefix+2])
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(messages[prefix+3])
            fmt.add_successful('create_namespace')

        ret = rcc.run(payloads['enable_forwardv4'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix+4])
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(messages[prefix+5])
        fmt.add_successful('enable_forwardv4')

        ret = rcc.run(payloads['enable_forwardv6'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix+6])
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(messages[prefix+7])
        fmt.add_successful('enable_forwardv6')

        ret = rcc.run(payloads['enable_lo'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix+8])
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(messages[prefix+9])
        fmt.add_successful('enable_lo')

        ret = rcc.run(payloads['find_lo1'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix+10])
        create_lo1 = True
        if ret["payload_code"] != SUCCESS_CODE:
            # No need to create lo1 if it exists already
            create_lo1 = False
        fmt.add_successful('find_lo1')

        if create_lo1:
            ret = rcc.run(payloads['create_lo1'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, messages[prefix+11])
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(messages[prefix+12])
        fmt.add_successful('create_lo1')

        ret = rcc.run(payloads['find_lo1_address'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix+13])
        create_lo1_address = True
        if ret["payload_code"] != SUCCESS_CODE:
            # No need to assign this address to lo1 if it has been assigned already
            create_lo1_address = False
        fmt.add_successful('find_lo1_address')

        if create_lo1_address:
            ret = rcc.run(payloads['create_lo1_address'])
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, messages[prefix+14])
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(messages[prefix+15])
            fmt.add_successful('create_lo1_address')

        ret = rcc.run(payloads['enable_lo1'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, messages[prefix+16])
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(messages[prefix+17])
        fmt.add_successful('enable_lo1')

        return True, "", successful_payloads


    status, msg, successful_payloads = run_podnet(enabled, 3020, {})
    if status == False:
        return status, msg

    status, msg = run_podnet(disabled, 3050, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1000]



def scrub(
        name: str,
        lo_addr='169.254.169.254',
        config_file=None,
) -> Tuple[bool, str]:
    """
    description:
        Removes a network name space from PodNet HA.

    parameters:
        name:
            description: network namespace's name
            type: string
            required: true
        lo_addr:
            description: IP address to assign to the namespace's loopback interface.
            type: string
            required: false
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

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Define messages

    messages = {
        1100: f'1100: Successfully removed name space {name} from both PodNet nodes.',
        3121: f'3121: Failed to connect to the enabled PodNet from the config file {config_file} for find_namespace_payload: ',
        3122: f'3122: Failed to connect to the enabled PodNet from the config file {config_file} for delete_namespace_payload: ',
        3123: f'3123: Failed to delete name space {name} on the enabled PodNet. Payload exited with status ',
        3131: f'3131: Successfully deleted name space {name} on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for find_namespace_payload: ',
        3132: f'3132: Successfully deleted name space {name} on enabled PodNet but failed to connect to the disabled PodNet '
              f'from the config file {config_file} for delete_namespace_payload: ',
        3133: f'3133: Successfully deleted name space {name} on enabled PodNet but failed to delete on the disabled PodNet. '
               'Payload exited with status ',
    }

    status, config_data, msg = load_pod_config(config_file)
    if not status:
      if config_data['raw'] is None:
          return False, msg
      else:
          return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
              indent=2,
              sort_keys=True)
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['enabled']

    name_grepsafe = name.replace('.', '\.')

    # define payloads
    find_namespace_payload = "ip netns list | grep -w '{name_grepsafe}'"
    delete_namespace_payload = "ip netns delete {name}"

    # call rcc comms_ssh on enabled PodNet
    ret = comms_ssh(
        host_ip=enabled,
        payload=find_namespace_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        return False, messages[3121] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {ret["channel_message"]}\nchannel_error: {ret["channel_error"]}'

    delete_namespace = False
    if ret["payload_code"] == SUCCESS_CODE:
        # No need to delete this name space if it exists already
        delete_namespace = True

    if delete_namespace:
      # call rcc comms_ssh on enabled PodNet
      ret = comms_ssh(
          host_ip=enabled,
          payload=delete_namespace_payload,
          username='robot',
      )
      if ret["channel_code"] != CHANNEL_SUCCESS:
          return False, messages[3122] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {ret["channel_message"]}\nchannel_error: {ret["channel_error"]}'
      if ret["payload_code"] != SUCCESS_CODE:
          return False, messages[3123]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    # call rcc comms_ssh on disabled PodNet
    ret = comms_ssh(
        host_ip=disabled,
        payload=find_namespace_payload,
        username='robot',
    )
    if channel_code != CHANNEL_SUCCESS:
        return False, messages[3131] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {ret["channel_message"]}\nchannel_error: {ret["channel_error"]}'

    delete_namespace = False
    if ret["payload_code"] == SUCCESS_CODE:
        # Only delete this name space if it exists
        delete_namespace = True

    if delete_namespace:
      # call rcc comms_ssh on disabled PodNet
      ret = comms_ssh(
          host_ip=disabled,
          payload=delete_namespace_payload,
          username='robot',
      )
      if ret["channel_code"] != CHANNEL_SUCCESS:
          return False, messages[3132] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {ret["channel_message"]}\nchannel_error: {ret["channel_error"]}'
      if ret["payload_code"] != SUCCESS_CODE:
          return False, messages[3133]  + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}'

    return True, messages[1000]


def read(
        name: str,
        lo_addr='169.254.169.254',
        config_file=None,
) -> Tuple[bool, dict, str]:
    """
    description:
        Reads cloud-init user data and meta data files for a virtual machine on
        PodNet HA (if any) and returns them.

    parameters:
        name:
            description: network namespace's name
            type: string
            required: true
        lo_addr:
            description: IP address to assign to the namespace's loopback interface.
            type: string
            required: false
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
                  entry:
                    description: |
                        the entry of the network name space in the list output by
                        `ip netns list`.
                    type: string
                  forwardv4:
                    description: content of net.ipv4.ip_forward sysctl in network name space
                    type: string
                  forwardv6:
                    description: content of net.ipv6.conf.all.forwarding sysctl in network name space
                    type: string
    """

    # Default config_file if it is None
    if config_file is None:
        config_file = '/opt/robot/config.json'

    # Define messages

    messages = {
        1200: f'1200: Successfully retrieved network name space {name} status from both PodNet nodes.',
        3221: f'3221: Failed to connect to the enabled PodNet from the config file {config_file} for find_namespace_payload: ',
        3222: f'3222: Failed to find name space {name} on the enabled PodNet. Payload exited with status ',
        3223: f'3223: Failed to connect to the enabled PodNet from the config file {config_file} for find_forwardv4_payload',
        3224: f'3224: Failed to run find_forwardv4_payload {name} on the enabled PodNet. Payload exited with status ',
        3225: f'3225: Unexpected value for sysctl net.ipv4.ip_forward in name space {name} on the enabled PodNet ',
        3226: f'3226: Failed to connect to the enabled PodNet from the config file {config_file} for find_forwardv6_payload: ',
        3227: f'3227: Failed to run {name} find_forwardv4_payload on the enabled PodNet. Payload exited with status ',
        3228: f'3228: Unexpected value for sysctl net.ipv6.conf.all.forwarding in name space {name} on the enabled PodNet ',
        3231: f'3231: Failed to connect to the disabled PodNet from the config file {config_file} for find_namespace_payload: ',
        3232: f'3232: Failed to find name space {name} on the disabled PodNet. Payload exited with status ',
        3233: f'3233: Failed to connect to the disabled PodNet for find_forwardv4_payload.: ',
        3234: f'3234: Failed to run find_forwardv4_payload on the disabled PodNet. Payload exited with status ',
        3235: f'3235: Value for sysctl net.ipv4.ip_forward on disabled PodNet is unexpected ',
        3236: f'3236: Failed to connect to the disabled PodNet from the config file {config_file} for find_forwardv6_payload: ',
        3237: f'3237: Failed to run find_forwardv6_payload on disabled PodNet. Payload exited with status ',
        3238: f'3238: Value for sysctl net.ipv6.conf.all.forwarding on disabled PodNet is unexpected ',
    }

    retval = True
    data_dict = None
    message_list = ()

    status, config_data, msg = load_pod_config(config_file)
    if not status:
      if config_data['raw'] is None:
          return False, msg
      else:
          return False, msg + "\nJSON dump of raw configuration:\n" + json.dumps(config_data['raw'],
              indent=2,
              sort_keys=True)
    enabled = config_data['processed']['enabled']
    disabled = config_data['processed']['enabled']

    name_grepsafe = name.replace('.', '\.')

    # define payloads
    find_namespace_payload = "ip netns list | grep -w '{name_grepsafe}'"
    find_forwardv4_payload = "ip netns exec {name} sysctl --write net.ipv4.ip_forward | awk '{print $3}"
    find_forwardv6_payload = "ip netns exec {name} sysctl --write net.ipv6.conf.all.forwarding | awk {print $3}'"

    # call rcc comms_ssh for name space retrieval from enabled PodNet
    ret = comms_ssh(
        host_ip=enabled,
        payload=find_namespace_payload,
        username='robot',
    )

    if ret["channel_code"] != CHANNEL_SUCCESS:
        retval = False
        message_list.append(messages[3221] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {ret["channel_message"]}\nchannel_error: {ret["channel_error"]}')

    if (ret["payload_code"] is not None) and (ret["payload_code"] != SUCCESS_CODE):
        retval = False
        message_list.append(messages[3222] + f'{payload_code}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}')
    else:
        data_dict[enabled]['entry'] = ret["payload_message"]

    # call rcc comms_ssh for IPv4 forwarding status retrieval from enabled PodNet
    ret = comms_ssh(
        host_ip=enabled,
        payload=find_forwardv4_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        retval = False
        message_list.append(messages[3223] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {ret["channel_message"]}\nchannel_error: {ret["channel_error"]}')

    if (ret["payload_code"] is not None) and (ret["payload_code"] != SUCCESS_CODE):
        retval = False
        message_list.append(messages[3224] + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}')
    else:
        if ret["payload_message"] != '1':
            retval = False
            message_list.append(messages[3225] + f'(is: {ret["payload_message"]}s, should be: `1`).')
        data_dict[enabled]['forwardv4'] = ret["payload_message"]

    # call rcc comms_ssh for IPv6 forwarding status retrieval from enabled PodNet
    ret = comms_ssh(
        host_ip=enabled,
        payload=find_forwardv6_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        retval = False
        message_list.append(messages[3226] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {ret["channel_message"]}\nchannel_error: {ret["channel_error"]}')

    if (ret["payload_code"] is not None) and (ret["payload_code"] != SUCCESS_CODE):
        retval = False
        message_list.append(messages[3227] + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}')
    else:
        if ret["payload_message"] != '1':
            retval = False
            message_list.append(messages[3228] + f'(is: {ret["payload_message"]}s, should be: `1`).')
        data_dict[enabled]['forwardv6'] = ret["payload_message"]

    # call rcc comms_ssh for name space retrieval from disabled PodNet
    ret = comms_ssh(
        host_ip=disabled,
        payload=find_namespace_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        retval = False
        message_list.append(messages[3231] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {ret["channel_message"]}\nchannel_error: {ret["channel_error"]}')

    if (ret["payload_code"] is not None) and (ret["payload_code"] != SUCCESS_CODE):
        retval = False
        message_list.append(messages[3232] + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}')
    else:
        data_dict[disabled]['entry'] = ret["payload_message"]

    # call rcc comms_ssh for IPv4 forwarding status retrieval from disabled PodNet
    ret = comms_ssh(
        host_ip=disabled,
        payload=find_forwardv4_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        retval = False
        message_list.append(messages[3233] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {ret["channel_message"]}\nchannel_error: {ret["channel_error"]}')

    if (ret["payload_code"] is not None) and (ret["payload_code"] != SUCCESS_CODE):
        retval = False
        message_list.append(messages[3234] + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}')
    else:
        if ret["payload_message"] != '1':
            retval = False
            message_list.append(messages[3235] + f'(is: {ret["payload_message"]}s, should be: `1`).')
        data_dict[disabled]['forwardv4'] = ret["payload_message"]

    # call rcc comms_ssh for IPv6 forwarding status retrieval from disabled PodNet
    ret = comms_ssh(
        host_ip=disabled,
        payload=find_forwardv6_payload,
        username='robot',
    )
    if ret["channel_code"] != CHANNEL_SUCCESS:
        retval = False
        message_list.append(messages[3236] + f'channel_code: {ret["channel_code"]}s.\nchannel_message: {ret["channel_message"]}\nchannel_error: {ret["channel_error"]}')

    if (ret["payload_code"] is not None) and (ret["payload_code"] != SUCCESS_CODE):
        retval = False
        message_list.append(messages[3237] + f'{ret["payload_code"]}s.\nSTDOUT: {ret["payload_message"]}\nSTDERR: {ret["payload_error"]}')
    else:
        if ret["payload_message"] != '1':
            retval = False
            message_list.append(messages[3238] + f'(is: {ret["payload_message"]}s, should be: `1`).')
        data_dict[disabled]['forwardv6'] = ret["payload_message"]

    message_list.append(messages[1200])
    return retval, data_dict, message_list
