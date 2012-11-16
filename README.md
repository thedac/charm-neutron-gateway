Overview
--------

Quantum provides flexible software defined networking (SDN) for OpenStack.

This charm is designed to be used in conjunction with the 'quantum-agent'
charm (and the rest of the OpenStack related charms in the charm store) to
virtualized the network that Nova Compute instances plug into.

Its designed as a replacement for nova-network; however it does not yet
support all of the features as nova-network (such as multihost) so may not
be suitable for all.

Quantum supports a rich plugin/extension framework for propriety networking
solutions and supports (in core) Nicira NVP, NEC, Cisco and others...

The charm currently only supports the fully free OpenvSwitch plugin and
implements the 'Provider Router with Private Networks' use case.

See the upstream [Quantum documentation](http://docs.openstack.org/trunk/openstack-network/admin/content/use_cases_single_router.html)
for more details.


Usage
-----

Assumming that you have already deployed OpenStack using Juju, Quantum can be
added to the mix:

    juju deploy quantum
    juju add-relation quantum mysql
    juju add-relation quantum rabbitmq-server
    juju add-relation keystone
    juju add-relation nova-cloud-controller

This will setup a Quantum API server and the DHCP and L3 routing agents on the
deployed servce unit.  ATM it does not support multiple units (WIP).

To then integrate Quantum with nova-compute do:

    juju deploy quantum-agent
    juju add-relation quantum-agent mysql
    juju add-relation quantum-agent rabbitmq-server
    juju add-relation quantum-agent nova-compute

All of the units supporting nova-compute will now be reconfigured to support
use of Quantum instead of nova-network.

Configuration
-------------

The quantum charm supports a number of configuration options; at a minimum you
will need to specify the external network configuration for you environment.
These are used to configure the 'external network' in quantum which provides
outbound public network access from tenant private networks and handles the
allocation of floating IP's for inbound public network access.

You will also need to provide the 'ext-port' configuration element; this should
be the port on the server which should be used for routing external/public
network traffic.  This does of course mean that you need a server with more than
one network interface to deploy the quantum charm.

Example minimal configuration:

    quantum:
      ext-port: eth1
      conf-ext-net: yes
      ext-net-cidr: 192.168.21.0/24
      ext-net-gateway: 192.168.21.1
      pool-floating-start: 192.168.21.130
      pool-floating-end: 192.168.21.200

The IP addresses above are for illustrative purposes only; in a real environment
these would be configured with actual routable public addresses.

TODO
----

 * Provide more network configuration use cases.
 * Support VLAN in addition to GRE+OpenFlow for L2 separation.
 * High Avaliability.
 * Support for propriety plugins for Quantum.

