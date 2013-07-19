
--------

Quantum provides flexible software defined networking (SDN) for OpenStack.

This charm is designed to be used in conjunction with the rest of the OpenStack
related charms in the charm store) to virtualized the network that Nova Compute
instances plug into.

Its designed as a replacement for nova-network; however it does not yet
support all of the features as nova-network (such as multihost) so may not
be suitable for all.

Quantum supports a rich plugin/extension framework for propriety networking
solutions and supports (in core) Nicira NVP, NEC, Cisco and others...

The Openstack charms currently only support the fully free OpenvSwitch plugin
and implements the 'Provider Router with Private Networks' use case.

See the upstream [Quantum documentation](http://docs.openstack.org/trunk/openstack-network/admin/content/use_cases_single_router.html)
for more details.


Usage
-----

In order to use Quantum with Openstack, you will need to deploy the
nova-compute and nova-cloud-controller charms with the network-manager
configuration set to 'Quantum':

    nova-cloud-controller:
        network-manager: Quantum

This decision must be made prior to deploying Openstack with Juju as
Quantum is deployed baked into these charms from install onwards:

    juju deploy nova-compute
    juju deploy --config config.yaml nova-cloud-controller
    juju add-relation nova-compute nova-cloud-controller

The Quantum Gateway can then be added to the deploying:

    juju deploy quantum-gateway
    juju add-relation quantum-gateway mysql
    juju add-relation quantum-gateway rabbitmq-server
    juju add-relation quantum-gateway nova-cloud-controller

The gateway provides two key services; L3 network routing and DHCP services.

These are both required in a fully functional Quantum Openstack deployment.

TODO
----

 * Provide more network configuration use cases.
 * Support VLAN in addition to GRE+OpenFlow for L2 separation.
