"""
Primitive for Global Network (Netplan interface config) on PodNet
"""
# stdlib
import logging
from typing import Tuple
# lib
from cloudcix.rcc import deploy_lsh, deploy_ssh, CouldNotConnectException
# local
from .utils import JINJA_ENV, check_template_data


__all__ = [
    'build',
]

BUILD_TEMPLATE = 'net/commands/build.sh.j2'
LOGGER = 'primitives.net'


def build(
        host: str,
        identifier: str,
        order: int,
        system_name: str,
        config_filepath=None,
        ips=None,
        mac=None,
        routes=None,
        vlan=None,
        vlan_ips=None,
        vlan_routes=None,
) -> Tuple[bool, str]:
    """
    description:
        1. Backups if /etc/netplan/<order>-<identifier>.yaml exists
        2. Creates /etc/netplan/<order>-<identifier>.yaml
        3. Verifies the changes(netplan generate), if failed then reverts the changes and exits
        4. Applies the changes(netplan apply)
        5. Removes the Backup file

    parameters:
        host:
            description: IP or dns name of the host where the interface is created on.
            type: string
            required: True
        identifier:
            description: The interface's custom name on the machine.
            type: string
            required: True
        order:
            description: To specify the order in which this interface added to networking services
            type: int
            required: True
        system_name:
            description: The interface's logical name on the machine.
            type: string
            required: True
        config_filepath:
            description: |
                Location of the json file with hardware settings. If one is not provided, the default path will be used
            type: string
        ips:
            description: List of IPaddresses defined on ethernet interface, in string format
            type: list
        mac:
            description: macaddress of the interface
            type: string
        routes:
            description: List of route objects defined on ethernet interface
            type: list
            properties:
                to:
                    description: IP addresses to which the traffic is destined
                    type: string
                via:
                    description: IP addresses from which the traffic is directed
        vlan:
            description: The number used to tag the identifier interface.
            type: int
        vlan_ips:
            description: List of IPaddresses defined on vlan interface, in string format
            type: list
        vlan_routes:
            description: List of route objects defined on vlan interface
            type: list
            properties:
                to:
                    description: IP addresses to which the traffic is destined
                    type: string
                via:
                    description: IP addresses from which the traffic is directed

    return:
        description: |
            A tuple with a boolean flag stating whether the build was successful or not and
            the payload from output and errors.
        type: tuple
    """

    # Access the logging level from the main program
    logger = logging.getLogger(f'{LOGGER}.build')
    logger.debug('Compiling data for net.build')

    # hardware data
    if config_filepath is None:
        config_filepath = '/etc/cloudcix/pod/configs/config.json'

    # netplan file
    netplan_filepath = f'/etc/netplan/{order}-{identifier}.yaml'

    # messages
    messages = {
        '000': f'Successfully built interface #{identifier} in network',
        '300': f'Failed to backup {netplan_filepath} to {netplan_filepath}.bak',
        '301': f'Failed to build interface #{identifier} to in network',
        '302': f'Failed to Generate netplan config.',
        '303': f'Failed to Apply netplan config.',
    }

    template_data = {
        'identifier': identifier,
        'ips': ips,
        'mac': mac,
        'messages': messages,
        'netplan_filepath': netplan_filepath,
        'routes': routes,
        'system_name': system_name,
        'vlan': vlan,
        'vlan_ips': vlan_ips,
        'vlan_routes': vlan_routes,
    }

    # ensure all the required keys are collected and no key has None value for template_data
    template = JINJA_ENV.get_template(BUILD_TEMPLATE)
    template_verified, template_error = check_template_data(template_data, template)
    if not template_verified:
        logger.debug(
            f'Failed to generate build bash script for Netplan Interface #{identifier}.\n{template_error}',
        )
        return False, template_error

    # Prepare public bridge build config
    bash_script = template.render(**template_data)
    logger.debug(
        f'Generated build bash script for Netplan Interface #{identifier}\n{bash_script}',
    )

    success, output = False, ''
    # Deploy the bash script to the Host
    try:
        if host in ['127.0.0.1', None, '', 'localhost']:
            stdout, stderr = deploy_lsh(
                payload=bash_script,
            )
        else:
            stdout, stderr = deploy_ssh(
                host_ip=host,
                payload=bash_script,
                username='robot',
            )
    except CouldNotConnectException as e:
        return False, str(e)

    if stdout:
        logger.debug(
            f'Netplan interface #{identifier} on #{host} build commands generated stdout.'
            f'\n{stdout}',
        )
        for code, message in messages.items():
            if message in stdout:
                output += message
                if int(code) < 100:
                    success = True

    if stderr:
        logger.error(
            f'Netplan interface #{identifier} on #{host} build commands generated stderr.'
            f'\n{stderr}',
        )
        output += stderr

    return success, output
