#!/usr/bin/python

import utils
import sys
import quantum_utils
import os


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
        utils.install('quantum-server',
                      'python-mysqldb',
                      *PLUGIN_PKGS[plugin])
    else:
        utils.juju_log('ERROR', 'Please provide a valid plugin config')
        sys.exit(1)


def config_changed():
    plugin = utils.config_get('plugin')
    if plugin in PLUGIN_PKGS.keys():
        render_api_paste_conf()
        render_quantum_conf()
        render_plugin_conf()
        if plugin == "ovs":
            # TODO: Defaults to Quantum Provider Router
            quantum_utils.add_bridge('br-int')
            quantum_utils.add_bridge('br-ex')
            ext_port = utils.config_get('ext-port')
            if ext_port:
                quantum_utils.add_bridge_port('br-ex', ext_port)
            render_l3_agent_conf()
            utils.restart('quantum-l3-agent',
                          'quantum-plugin-openvswitch-agent',
                          'quantum-dhcp-agent')
        utils.restart('quantum-server')
    else:
        utils.juju_log('ERROR',
                       'Please provide a valid plugin config')
        sys.exit(1)


def upgrade_charm():
    install()
    config_changed()


def render_l3_agent_conf():
    context = get_keystone_conf()
    if context:
        with open(quantum_utils.L3_AGENT_CONF, "w") as conf:
            conf.write(utils.render_template("l3_agent.ini", context))


def render_api_paste_conf():
    context = get_keystone_conf()
    if context:
        with open(quantum_utils.QUANTUM_API_CONF, "w") as conf:
            conf.write(utils.render_template("api-paste.ini", context))


def render_quantum_conf():
    context = get_rabbit_conf()
    if context:
        context['core_plugin'] = \
            quantum_utils.CORE_PLUGIN[utils.config_get('plugin')]
        with open(quantum_utils.QUANTUM_CONF, "w") as conf:
            conf.write(utils.render_template("quantum.conf", context))


def render_plugin_conf():
    context = get_db_conf()
    if context:
        context['local_ip'] = utils.get_host_ip()
        plugin = utils.config_get('plugin')
        conf_file = quantum_utils.PLUGIN_CONF[plugin]
        with open(conf_file, "w") as conf:
            conf.write(utils.render_template(os.path.basename(conf_file),
                                             context))


def keystone_joined():
    url = "http://{}:9696/".format(utils.unit_get('private-address'))
    utils.relation_set(service="quantum",
                       region="RegionOne",
                       public_url=url,
                       admin_url=url,
                       internal_url=url)


def keystone_changed():
    if os.path.exists(quantum_utils.L3_AGENT_CONF):
        render_l3_agent_conf()  # Restart quantum_l3_agent
        utils.restart('quantum-l3-agent')
    render_api_paste_conf()  # Restart quantum server
    utils.restart('quantum-server')
    if os.path.exists(quantum_utils.DHCP_AGENT_CONF):
        utils.restart('quantum-dhcp-agent')
    notify_agents()


def get_keystone_conf():
    for relid in utils.relation_ids('identity-service'):
        for unit in utils.relation_list(relid):
            conf = {
                "keystone_host": utils.relation_get('private-address',
                                                    unit, relid),
                "token": utils.relation_get('admin_token', unit, relid),
                "service_port": utils.relation_get('service_port',
                                                   unit, relid),
                "auth_port": utils.relation_get('auth_port', unit, relid),
                "service_username": utils.relation_get('service_username',
                                                       unit, relid),
                "service_password": utils.relation_get('service_password',
                                                       unit, relid),
                "service_tenant": utils.relation_get('service_tenant',
                                                     unit, relid)
                }
            if None not in conf.itervalues():
                return conf
    return None


def db_joined():
    utils.relation_set(username=quantum_utils.DB_USER,
                       database=quantum_utils.QUANTUM_DB,
                       hostname=utils.unit_get('private-address'))


def db_changed():
    render_plugin_conf()
    utils.restart('quantum-server')
    if utils.config_get('plugin') == 'ovs':
        utils.restart('quantum-plugin-openvswitch-agent')


def get_db_conf():
    for relid in utils.relation_ids('shared-db'):
        for unit in utils.relation_list(relid):
            conf = {
                "host": utils.relation_get('private-address',
                                           unit, relid),
                "user": quantum_utils.DB_USER,
                "password": utils.relation_get('password',
                                               unit, relid),
                "db": quantum_utils.QUANTUM_DB
                }
            if None not in conf.itervalues():
                return conf
    return None


def amqp_joined():
    utils.relation_set(username=quantum_utils.RABBIT_USER,
                       vhost=quantum_utils.RABBIT_VHOST)


def amqp_changed():
    render_quantum_conf()
    utils.restart('quantum-server', 'quantum-dhcp-agent')
    if utils.config_get('plugin') == 'ovs':
        utils.restart('quantum-plugin-openvswitch-agent')


def get_rabbit_conf():
    for relid in utils.relation_ids('amqp'):
        for unit in utils.relation_list(relid):
            conf = {
                "rabbit_host": utils.relation_get('private-address',
                                                  unit, relid),
                "rabbit_virtual_host": quantum_utils.RABBIT_VHOST,
                "rabbit_userid": quantum_utils.RABBIT_USER,
                "rabbit_password": utils.relation_get('password',
                                                      unit, relid)
                }
            if None not in conf.itervalues():
                return conf
    return None


def nm_joined():
    keystone_conf = get_keystone_conf()
    if keystone_conf:
        utils.relation_set(**keystone_conf)  # IGNORE:W0142
    utils.relation_set(plugin=utils.config_get('plugin'))


def notify_agents():
    keystone_conf = get_keystone_conf()
    if keystone_conf:
        for relid in utils.relation_ids('network-manager'):
            utils.relation_set(relid=relid,
                               plugin=utils.config_get('plugin'),
                               **keystone_conf)


utils.do_hooks({
    "install": install,
    "config-changed": config_changed,
    "upgrade-charm": upgrade_charm,
    "identity-service-relation-joined": keystone_joined,
    "identity-service-relation-changed": keystone_changed,
    "shared-db-relation-joined": db_joined,
    "shared-db-relation-changed": db_changed,
    "amqp-relation-joined": amqp_joined,
    "amqp-relation-changed": amqp_changed,
    "network-manager-relation-joined": nm_joined,
    })

sys.exit(0)
