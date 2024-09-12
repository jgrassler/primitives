"""
Primitive for Storage drives (QEMU images) on KVM hosts
"""

# stdlib
from typing import Tuple
# lib
from cloudcix.rcc import comms_ssh, CouldNotConnectException


__all__ = [
    'build',
    'scrub',
    'updatequiesced',
    'updaterunning',
]

SUCCESS_CODE = 0


def build(
        host: str,
        domain_path: str,
        storage: str,
        size: int,
) -> Tuple[bool, str]:
    """
    description:
        Creates <domain_path><storage> file on the given Host <host>.

    parameters:
        host:
            description: The dns or ipadddress of the Host on which this storage_kvm is built
            type: string
            required: true
        domain_path:
            description: The location or directory path where this storage_kvm is created
            type: string
            required: true
        storage:
            description: The unique name of the storage_kvm to be created
            type: string
            required: true
        size:
            description: The size of the storage_kvm to be created, must be in GB value 
            type: int
            required: true
    return:
        description: |
            A tuple with a boolean flag stating the build was successful or not and
            the output or error message.
        type: tuple
    """
    # Define message
    messages = {
        1000: f'1000: Successfully created storage {storage}',
        3021: f'3021: Failed to connect to the host {host}',
        3022: f'3022: Failed to create storage_kvm {domain_path}{storage} on the host {host}'
    }

    # Define payload
    payload = f'qemu-img create -f qcow2 {domain_path}{storage} {size}G'

    # Create storage using SSH communication
    try:
        create_storage_kvm, stdout, stderr = comms_ssh(
            host_ip=host,
            payload=payload,
            username='robot',
        )
    except CouldNotConnectException:
        return False, messages[3021]

    if create_storage_kvm.exit_code != SUCCESS_CODE:
        return False, messages[3022]

    return True, messages[1000]


def scrub():
    return(False, 'Not Implemted')


def updatequiesced():
    return(False, 'Not Implemted')


def updaterunning():
    return(False, 'Not Implemted')
