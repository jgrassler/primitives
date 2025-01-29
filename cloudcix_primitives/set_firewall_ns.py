# stdlib
from typing import Tuple, Literal
import json
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh, CONNECTION_ERROR, VALIDATION_ERROR
# local
from cloudcix_primitives.utils import load_pod_config, PodnetErrorFormatter, SSHCommsWrapper


__all__ = [
    'build',
    'read',
    'scrub',
    'update',
]

SUCCESS_CODE = 0


def build(
    namespace: str,
    name: str,
    type: Literal['ipv4_addr', 'ipv6_addr'],
    config_file=None
) -> Tuple[bool, str]:
    messages = {
        1000: f'1000: Successfully created named nftables set {name} inside namespace {namespace} for type {type}',

        3021: f'3021: Failed to connect to the enabled PodNet for payload set_add:  ',
        3022: f'3022: Failed to create named nftables set {name} inside namespace {namespace} on the enabled PodNet for payload set_add:  ',

        3051: f'3051: Failed to connect to the disabled PodNet for payload set_add:  ',
        3052: f'3052: Failed to create named nftables set {name} inside namespace {namespace} on the disabled PodNet for payload set_add:  '
    }

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
            # 'set_check': f'ip netns exec {namespace} nft list set inet FILTER {name}',
            'set_add': f'ip netns exec {namespace} nft add set inet FILTER {name} {{ type {type}\\; flags interval\\; auto-merge\\; }}'
        }

        ret = rcc.run(payloads['set_add'])
        if ret['channel_code'] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix+1}: {messages[prefix+1]}')
        if ret['payload_code'] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix+2}: {messages[prefix+2]}')
        fmt.add_successful('set_add', ret)

        return True, "", fmt.successful_payloads
    
    status, msg, successful_payloads = run_podnet(enabled, 3020, {})
    if status == False:
        return status, msg
    
    status, msg, successful_payloads = run_podnet(disabled, 3050, successful_payloads)
    if status == False:
        return status, msg
    
    return True, messages[1000] + '\n' + msg
        


def read(
    namespace: str,
    name: str,
    config_file=None,
) -> Tuple[bool, dict, str]:
    messages = {
    }

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

    def run_podnet(podnet_node, prefix, successful_payloads, data_dict):
        rcc = SSHCommsWrapper(comms_ssh, podnet_node, 'robot')
        fmt = PodnetErrorFormatter(
            config_file,
            podnet_node,
            podnet_node == enabled,
            {'payload_message': 'STDOUT', 'payload_error': 'STDERR'},
            successful_payloads
        )

        return True, "", fmt.successful_payloads, data_dict
    
    status, 


def scrub(
    namespace: str,
    name: str,
    config_file=None
) -> Tuple[bool, str]:
    messages = {
        1100: f'1000: Successfully removed named nftables set {name} inside namespace {namespace}',

        3121: f'3121: Failed to connect to the enabled PodNet for set_destroy payload:  ',
        3122: f'3122: Failed to removed named nftables set {name} inside namespace {namespace} on the enabled PodNet for payload set_destroy:  ',

        3151: f'3151: Failed to connect to the disabled PodNet for set_destroy payload:  ',
        3152: f'3152: Failed to removed named nftables set {name} inside namespace {namespace} on the disabled PodNet for payload set_destroy:  ',
    }
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
            'set_destroy': f'ip netns exec {namespace} nft destroy inet FILTER {name}'
        }

        ret = rcc.run(payloads['set_destroy'])
        if ret['channel_code'] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix+1}: {messages[prefix+1]}')
        if ret['payload_code'] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix+2}: {messages[prefix+2]}')
        fmt.add_successful('set_destroy', ret)

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled, 3120, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3150, successful_payloads)
    if status == False:
        return status, msg
    
    return True, messages[1100] + '\n' + msg


def update(
    namespace: str,
    name: str,
    elements: str,
    config_file=None
) -> Tuple[bool, str]:
    messages = {
        1300: f'1300: Successfully updated named nftables set {name} inside namespace {namespace}',

        3321: f'3321: Failed to connect to the enabled PodNet for set_flush payload:  ',
        3322: f'3322: Failed to flush named nftables set {name} inside namespace {namespace} on the enabled PodNet for payload set_flush:  ',
        3323: f'3323: Failed to connect to the enabled PodNet for set_add_element payload:  ',
        3324: f'3324: Failed to add {elements} to named nftables set {name} inside namespace {namespace} on the enabled PodNet for payload set_add_element:  ',

        3351: f'3351: Failed to connect to the disabled PodNet for set_flush payload:  ',
        3352: f'3352: Failed to flush named nftables set {name} inside namespace {namespace} on the disabled PodNet for payload set_flush:  ',
        3353: f'3353: Failed to connect to the disabled PodNet for set_add_element payload:  ',
        3354: f'3354: Failed to add {elements} to named nftables set {name} inside namespace {namespace} on the disabled PodNet for payload set_add_element:  ',
    }
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
            'set_flush': f'ip netns exec {namespace} nft flush set inet FILTER {name}',
            'set_add_element': f'ip netns exec {namespace} nft add element inet FILTER {name} {{ {elements} }}'
        }

        ret = rcc.run(payloads['set_flush'])
        if ret['channel_code'] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix+1}: {messages[prefix+1]}')
        if ret['payload_code'] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix+2}: {messages[prefix+2]}')
        fmt.add_successful('set_flush', ret)

        ret = rcc.run(payloads['set_add_element'])
        if ret['channel_code'] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f'{prefix+3}: {messages[prefix+3]}')
        if ret['payload_code'] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f'{prefix+4}: {messages[prefix+4]}')
        fmt.add_successful('set_add_element')

        return True, "", fmt.successful_payloads

    status, msg, successful_payloads = run_podnet(enabled, 3320, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3350, successful_payloads)
    if status == False:
        return status, msg
    
    return True, messages[1300]
