# Primitives

## direcotymain
Primitive to Build and Delete directories on PodNet HA

supported verbs:

- build:
    - path: str
    - config_file=None

- read:
    - path: str
    - config_file=None
    
- scrub:
    - path: str
    - config_file=None

## storage_kvm
Primitive for Storage drives (QEMU images) on KVM hosts

supported verbs:

- build:
    - host: str
    - domain_path: str
    - storage: str
    - size: int

- read:
    - host: str
    - domain_path: str
    - storage: str
    
- scrub:
    - host: str
    - domain_path: str
    - storage: str

- update:
    - host: str
    - domain_path: str
    - storage: str
    - size: int