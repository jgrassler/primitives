# Development

## Development Environment

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

You can mostly edit the code in this repository to your heart's content, commit
it and push it. The only problem arises when you add new files to the code
base. In this case, you have to run `pip install -e .` (substitute `.` by the
path to this repository as needed) again in the virtualenv. Otherwise, these
files will not be available.

## Helpers and Utilities

We have a small library of utility functions to make primitive development
easier. Refer to the inline documentation of `cloudcix_primitives.utils` to
learn about them.


## Templates

Right now, `cloudcix_primitives.ns` is our reference implementation for a
primitive. Please use this primitive as a template when developing new
primitives.
