#!/usr/bin/python

import utils
import sys
import quantum_utils


PLUGIN_PKGS = {
    "ovs": [  # TODO: Assumes Quantum Provider Gateway
        "quantum-plugin-openvswitch",
        "quantum-plugin-openvswitch-agent",
        "quantum-l3-agent",
        "quantum-dhcp-agent"
        ],
    "nvp": ["quantum-plugin-nicira"]  # No agent required
    }


def install():
    utils.configure_source()
    # TODO: when using the nicira plugin /etc/default/quantum-server
    # will also need to be updated to point to the correct configuration
    plugin = utils.config_get('plugin')
    if plugin in PLUGIN_PKGS.keys():
        if plugin == "ovs":
            # Install OVS DKMS first to ensure that the ovs module
            # loaded supports GRE tunnels
            utils.install('openvswitch-datapath-dkms')
        utils.install(['quantum-server'].extend(PLUGIN_PKGS[plugin]))
    else:
        utils.juju_log('ERROR', 'Please provide a valid plugin config')
        sys.exit(1)


def config_changed():
    plugin = utils.config_get('plugin')
    if plugin in PLUGIN_PKGS.keys():
        if plugin == "ovs":
            # TODO: Defaults to Quantum Provider Router
            quantum_utils.add_bridge('br-int')
            quantum_utils.add_bridge('br-ext')
            ext_port = utils.config_get('ext-port')
            if ext_port:
                quantum_utils.add_bridge_port('br-ex', ext_port)
            quantum_utils.configure_core_plugin(plugin)
            quantum_utils.configure_local_ip(plugin,
                                             utils.unit_get('private-address'))
    else:
        utils.juju_log('ERROR',
                       'Please provide a valid plugin config')
        sys.exit(1)


def keystone_joined():
    url = "http://{}:9696/".format(utils.unit_get('private-address'))
    utils.relation_set(service="quantum",
                       region="RegionOne",
                       public_url=url,
                       admin_url=url,
                       internal_url=url)


def keystone_changed():
    token = utils.relation_get('admin_token')
    service_port = utils.relation_get('service_port')
    auth_port = utils.relation_get('auth_port')
    service_username = utils.relation_get('service_username')
    service_password = utils.relation_get('service_password')
    service_tenant = utils.relation_get('service_tenant')
    if not (token and
            service_port and
            auth_port and
            service_username and
            service_password and
            service_tenant):
        utils.juju_log('INFO',
                       'keystone peer not ready yet')
        return
    if token == "-1":
        utils.juju_log('ERROR',
                       'Admin token error')
        sys.exit(1)
    keystone_host = utils.relation_get('private-address')
    utils.juju_log('INFO', 'Configuring quantum for keystone authentication')
    quantum_utils.configure_keystone(keystone_host,
                                     token,
                                     service_port,
                                     auth_port,
                                     service_username,
                                     service_password,
                                     service_tenant)


def db_joined():
    utils.relation_set(username=quantum_utils.DB_USER,
                       database=quantum_utils.QUANTUM_DB,
                       hostname=utils.unit_get('private-address'))


def db_changed():
    host = utils.relation_get('private-address')
    password = utils.relation_get('password')
    if not (host and password):
        return
    else:
        quantum_utils.configure_db_connection(utils.config_get('plugin'),
                                              host, password)


def amqp_joined():
    pass


def amqp_changed():
    pass


utils.do_hooks({
    "install": install,
    "config-changed": config_changed,
    "identity-service-relation-joined": keystone_joined,
    "identity-service-relation-changed": keystone_changed,
    "shared-db-relation-joined": db_joined,
    "shared-db-relation-changed": db_changed,
    "amqp-relation-joined": amqp_joined,
    "amqp-relation-changed": amqp_changed
    })

sys.exit(0)
