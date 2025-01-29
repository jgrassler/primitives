# stdlib
import json
from typing import Tuple
# lib
from cloudcix.rcc import CHANNEL_SUCCESS, comms_ssh, CONNECTION_ERROR, VALIDATION_ERROR
# local
from cloudcix_primitives.utils import load_pod_config, PodnetErrorFormatter, SSHCommsWrapper


__all__ = [
    'build',
    'read',
    'scrub',
]

SUCCESS_CODE = 0

def build(
        namespace: str,
        one_to_one: dict,
        ranges: list,
        public_ip_ns: str,
        config_file=None,
) -> Tuple[bool, str]:
    """
    description:
        Builds nftables tables, base chains, user chains, interface sets, jump
        rules and default base chain rules required for a CloudCIX project.
        Throughout the life time of a project, the base chains are never
        modified by another primitive. The user chains are managed by user
        chain primitives such as project_firewall_ns or nat_firewall_ns.

    parameters:
        namespace:
            description: VRF network name space's identifier, such as 'VRF453
            type: string
            required: true
        one_to_one:
          description: List of 1:1 mapping dictonaries from private IP address to public IP address. May be empty.
          type: list
          properties:
            private:
                description:
                    The private IP address to map to a public IP address.
            public:
                description:
                    The public IP address a private IP address is mapped to.
          required: true
        ranges
          description: flat list of IP addresses to map to the name space's public IP address. May be empty.
          type: list
          required: true
        public_ip_ns:
          description: the name space's pulic IP address.
          type: str
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

    messages = {
    1000: f'1000: Successfully created default firewall in project name space {namespace} on both PodNet nodes.',

    3021: f'Failed to connect to the enabled PodNet for flush_postrouting payload: ',
    3022: f'Failed to run flush_postrouting payload on the enabled PodNet. Payload exited with status ',
    3023: f'Failed to connect to the enabled PodNet for flush_prerouting payload: ',
    3024: f'Failed to run flush_prerouting payload on the enabled PodNet. Payload exited with status ',
    3025: f'Failed to connect to the enabled PodNet for postrouting_11 payload (%(payload)s): ',
    3026: f'Failed to run postrouting_11 payload (%(payload)s) on the enabled PodNet. Payload exited with status ',
    3027: f'Failed to connect to the enabled PodNet for prerouting_11 payload (%(payload)s): ',
    3028: f'Failed to run prerouting_11 payload (%(payload)s) on the enabled PodNet. Payload exited with status ',
    3029: f'Failed to connect to the enabled PodNet for range payload (%(payload)s): ',
    3030: f'Failed to run range payload (%(payload)s) on the enabled PodNet. Payload exited with status ',

    3061: f'Failed to connect to the enabled PodNet for flush_postrouting payload: ',
    3062: f'Failed to run flush_postrouting payload on the enabled PodNet. Payload exited with status ',
    3063: f'Failed to connect to the enabled PodNet for flush_prerouting payload: ',
    3064: f'Failed to run flush_prerouting payload on the enabled PodNet. Payload exited with status ',
    3065: f'Failed to connect to the enabled PodNet for postrouting_11 payload (%(payload)s): ',
    3066: f'Failed to run postrouting_11 payload (%(payload)s) on the enabled PodNet. Payload exited with status ',
    3067: f'Failed to connect to the enabled PodNet for prerouting_11 payload (%(payload)s): ',
    3068: f'Failed to run prerouting_11 payload (%(payload)s) on the enabled PodNet. Payload exited with status ',
    3069: f'Failed to connect to the enabled PodNet for range payload (%(payload)s): ',
    3070: f'Failed to run range payload (%(payload)s) on the enabled PodNet. Payload exited with status ',
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
            'flush_postrouting': f'ip netns exec ns1100 nft flush inet NAT POSTROUTING',
            'flush_prerouting': f'ip netns exec ns1100 nft flush inet NAT PREROUTING',
        }


        rule_templates = {
          'prerouting_11': f'ip netns exec {namespace} '
                           'nft add rule ip NAT POSTROUTING ip saddr %(private)s snat to %(public)s',
          'postrouting_11': f'ip netns exec {namespace} '
                            'nft add rule ip NAT PREROUTING ip saddr %(private)s snat to %(public)s',
          'range': f'ip netns exec {namespace} '
                   f'nft add rule ip NAT POSTROUTING ip saddr %(network)s snat to {public_ip_ns}'
        }

        ret = rcc.run(payloads['flush_postrouting'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        fmt.add_successful('flush_postrouting', ret)

        ret = rcc.run(payloads['flush_prerouting'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+3}: " + messages[prefix+3]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+4}: " + messages[prefix+4]), fmt.successful_payloads
        fmt.add_successful('flush_prerouting', ret)

        for mapping in one_to_one:
            payload_prerouting = rule_templates['prerouting_11'] % mapping
            payload_postrouting = rule_templates['prerouting_11'] % mapping

            ret = rcc.run(payload_postrouting)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+5}: " + messages[prefix+5] % {'payload': payload_postrouting}, fmt.successful_payloads)
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+6}: " + messages[prefix+6] % {'payload': payload_postrouting}, fmt.successful_payloads)
            fmt.add_successful('postrouting_11 (%s)' % payload_postrouting, ret)

            ret = rcc.run(payload_prerouting)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+7}: " + messages[prefix+7] % {'payload': payload_prerouting}, fmt.successful_payloads)
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+8}: " + messages[prefix+8] % {'payload': payload_prerouting}, fmt.successful_payloads)
            fmt.add_successful('prerouting_11 (%s)' % payload_prerouting, ret)

        for network in ranges:
            payload = rule_templates['range'] % {'network': network}

            ret = rcc.run(payload)
            if ret["channel_code"] != CHANNEL_SUCCESS:
                return False, fmt.channel_error(ret, f"{prefix+9}: " + messages[prefix+9] % {'payload': payload}, fmt.successful_payloads)
            if ret["payload_code"] != SUCCESS_CODE:
                return False, fmt.payload_error(ret, f"{prefix+10}: " + messages[prefix+10] % {'payload': payload}, fmt.successful_payloads)
            fmt.add_successful('range (%s)' % payload, ret)

        return True, "", fmt.successful_payloads


    status, msg, successful_payloads = run_podnet(enabled, 3020, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3060, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1000]


def read() -> Tuple[bool, dict, str]:
    return(False, {}, 'Not Implemented')


def scrub(
    namespace: str,
    config_file=None
    ) -> Tuple[bool, str]:
    """
    description:
        Builds nftables tables, base chains, user chains, interface sets, jump
        rules and default base chain rules required for a CloudCIX project.
        Throughout the life time of a project, the base chains are never
        modified by another primitive. The user chains are managed by user
        chain primitives such as project_firewall_ns or nat_firewall_ns.

    parameters:
        namespace:
            description: VRF network name space's identifier, such as 'VRF453
            type: string
            required: true
        public_bridge:
          description: the name space's public bridge interface's name, such as 'br-B1'.
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

    messages = {
    1000: f'1000: Successfully scrubbed default firewall in project name space {namespace} on both PodNet nodes.',

    3121: f'Failed to connect to the enabled PodNet for flush_ruleset payload: ',
    3122: f'Failed to run flush_ruleset payload on the enabled PodNet. Payload exited with status ',
    3161: f'Failed to connect to the disabled PodNet for flush_ruleset payload: ',
    3162: f'Failed to run flush_ruleset payload on the disabled PodNet. Payload exited with status ',
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
            'flush_ruleset': f'ip netns exec {namespace} nft flush ruleset'
        }

        ret = rcc.run(payloads['flush_ruleset'])
        if ret["channel_code"] != CHANNEL_SUCCESS:
            return False, fmt.channel_error(ret, f"{prefix+1}: " + messages[prefix+1]), fmt.successful_payloads
        if ret["payload_code"] != SUCCESS_CODE:
            return False, fmt.payload_error(ret, f"{prefix+2}: " + messages[prefix+2]), fmt.successful_payloads
        fmt.add_successful('flush_ruleset', ret)
        return True, "", fmt.successful_payloads


    status, msg, successful_payloads = run_podnet(enabled, 3120, {})
    if status == False:
        return status, msg

    status, msg, successful_payloads = run_podnet(disabled, 3160, successful_payloads)
    if status == False:
        return status, msg

    return True, messages[1000]
