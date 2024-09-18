# Development Environment

When developing primitives, you can set up an editable development environment
on a CloudCIX Appliance or any machine that fullfils two requirements:

1) The ability to ssh to both of the environment's PodNet nodes and other
   relevant machines, such as hypervisors as the robot user in a passwordless
   manner.

2) A config.json for PodNet. On a CloudCIX Appliance you'll find this in
   `/etc/cloudcix/pod/configs/config.json`.

The the `tools/setup-testenv.sh` script will do all the neccessary setup steps for you.
Just point it at an empty or non-existent directory...

```
setup-testenv.sh myvenv
```

...and it will set up a development virtual environment for you. Once that is
done, you can activate the virtual environment as follows:

```
. myvenv/bin/activate
```

Now you can run test scripts such as `tools/test_ns_primitive.py` as long as
you remain in the shell where you sourced the `activate` script:

```
$ tools/test_ns_primitive.py build mytestns
Status: True

Message:
Successfully created network name space mytestns on both PodNet nodes.
```

The `cloudcix_primitive` code being run will be drawn from this repository and
you can freely edit, commit and push it as you do your testing.

# Primitives

## directorymain
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
    
## firewallns
Primitive to Build and Delete nftables tables of Network Namespace on PodNet HA

supported verbs:

- build:
    - namespace: str
    - table: str
    - priority: int
    - config_file=None
    - rules: optional array
        - version: int
          source: array
            - str
          destination: array
            - str
          protocol: str
          port: array
            - str
          action: bool
          log: bool
          iiface: str
          oiface: str
          order: int
    - nats: dict
        dnats: optional array
            - public: str
              private: str
              iiface: str
        snats: optional array
            - public: str
              private: str
              oiface: str            

## storage_kvm
Primitive for Storage drives (QEMU images) on KVM hosts
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

