#!/usr/bin/python

import lib.utils as utils
import lib.cluster_utils as cluster
import sys
import quantum_utils as qutils
import os

PLUGIN = utils.config_get('plugin')


def install():
    utils.configure_source()
    if PLUGIN in qutils.GATEWAY_PKGS.keys():
        if PLUGIN == qutils.OVS:
            # Install OVS DKMS first to ensure that the ovs module
            # loaded supports GRE tunnels
            utils.install('openvswitch-datapath-dkms')
        utils.install(*qutils.GATEWAY_PKGS[PLUGIN])
    else:
        utils.juju_log('ERROR', 'Please provide a valid plugin config')
        sys.exit(1)


@utils.inteli_restart(qutils.RESTART_MAP)
def config_changed():
    if PLUGIN in qutils.GATEWAY_PKGS.keys():
        render_quantum_conf()
        render_dhcp_agent_conf()
        render_l3_agent_conf()
        render_metadata_agent_conf()
        render_metadata_api_conf()
        render_plugin_conf()
        render_ext_port_upstart()
        render_evacuate_unit()
        if PLUGIN == qutils.OVS:
            qutils.add_bridge(qutils.INT_BRIDGE)
            qutils.add_bridge(qutils.EXT_BRIDGE)
            ext_port = utils.config_get('ext-port')
            if ext_port:
                qutils.add_bridge_port(qutils.EXT_BRIDGE, ext_port)
    else:
        utils.juju_log('ERROR',
                       'Please provide a valid plugin config')
        sys.exit(1)


def upgrade_charm():
    install()
    config_changed()


def render_ext_port_upstart():
    if utils.config_get('ext-port'):
        with open(qutils.EXT_PORT_CONF, "w") as conf:
            conf.write(utils.render_template(
                            os.path.basename(qutils.EXT_PORT_CONF),
                            {"ext_port": utils.config_get('ext-port')}
                            )
                       )
    else:
        if os.path.exists(qutils.EXT_PORT_CONF):
            os.remove(qutils.EXT_PORT_CONF)


def render_l3_agent_conf():
    context = get_keystone_conf()
    if (context and
        os.path.exists(qutils.L3_AGENT_CONF)):
        with open(qutils.L3_AGENT_CONF, "w") as conf:
            conf.write(utils.render_template(
                            os.path.basename(qutils.L3_AGENT_CONF),
                            context
                            )
                       )


def render_dhcp_agent_conf():
    if (os.path.exists(qutils.DHCP_AGENT_CONF)):
        with open(qutils.DHCP_AGENT_CONF, "w") as conf:
            conf.write(utils.render_template(
                            os.path.basename(qutils.DHCP_AGENT_CONF),
                            {}
                            )
                       )


def render_metadata_agent_conf():
    context = get_keystone_conf()
    if (context and
        os.path.exists(qutils.METADATA_AGENT_CONF)):
        context['local_ip'] = utils.get_host_ip()
        context['shared_secret'] = qutils.get_shared_secret()
        with open(qutils.METADATA_AGENT_CONF, "w") as conf:
            conf.write(utils.render_template(
                            os.path.basename(qutils.METADATA_AGENT_CONF),
                            context
                            )
                       )


def render_quantum_conf():
    context = get_rabbit_conf()
    if (context and
        os.path.exists(qutils.QUANTUM_CONF)):
        context['core_plugin'] = \
            qutils.CORE_PLUGIN[PLUGIN]
        with open(qutils.QUANTUM_CONF, "w") as conf:
            conf.write(utils.render_template(
                            os.path.basename(qutils.QUANTUM_CONF),
                            context
                            )
                       )


def render_plugin_conf():
    context = get_quantum_db_conf()
    if (context and
        os.path.exists(qutils.PLUGIN_CONF[PLUGIN])):
        context['local_ip'] = utils.get_host_ip()
        conf_file = qutils.PLUGIN_CONF[PLUGIN]
        with open(conf_file, "w") as conf:
            conf.write(utils.render_template(
                            os.path.basename(conf_file),
                            context
                            )
                       )


def render_metadata_api_conf():
    context = get_nova_db_conf()
    r_context = get_rabbit_conf()
    q_context = get_keystone_conf()
    if (context and r_context and q_context and
        os.path.exists(qutils.NOVA_CONF)):
        context.update(r_context)
        context.update(q_context)
        context['shared_secret'] = qutils.get_shared_secret()
        with open(qutils.NOVA_CONF, "w") as conf:
            conf.write(utils.render_template(
                            os.path.basename(qutils.NOVA_CONF),
                            context
                            )
                       )


def render_evacuate_unit():
    context = get_keystone_conf()
    if context:
        with open('/usr/local/bin/quantum-evacuate-unit', "w") as conf:
            conf.write(utils.render_template('evacuate_unit.py', context))
        os.chmod('/usr/local/bin/quantum-evacuate-unit', 0700)


def get_keystone_conf():
    for relid in utils.relation_ids('quantum-network-service'):
        for unit in utils.relation_list(relid):
            conf = {
                "keystone_host": utils.relation_get('keystone_host',
                                                    unit, relid),
                "service_port": utils.relation_get('service_port',
                                                   unit, relid),
                "auth_port": utils.relation_get('auth_port', unit, relid),
                "service_username": utils.relation_get('service_username',
                                                       unit, relid),
                "service_password": utils.relation_get('service_password',
                                                       unit, relid),
                "service_tenant": utils.relation_get('service_tenant',
                                                     unit, relid),
                "quantum_host": utils.relation_get('quantum_host',
                                                   unit, relid),
                "quantum_port": utils.relation_get('quantum_port',
                                                   unit, relid),
                "quantum_url": utils.relation_get('quantum_url',
                                                   unit, relid),
                "region": utils.relation_get('region',
                                             unit, relid)
                }
            if None not in conf.itervalues():
                return conf
    return None


def db_joined():
    utils.relation_set(quantum_username=qutils.DB_USER,
                       quantum_database=qutils.QUANTUM_DB,
                       quantum_hostname=utils.unit_get('private-address'),
                       nova_username=qutils.NOVA_DB_USER,
                       nova_database=qutils.NOVA_DB,
                       nova_hostname=utils.unit_get('private-address'))


@utils.inteli_restart(qutils.RESTART_MAP)
def db_changed():
    render_plugin_conf()
    render_metadata_api_conf()


def get_quantum_db_conf():
    for relid in utils.relation_ids('shared-db'):
        for unit in utils.relation_list(relid):
            conf = {
                "host": utils.relation_get('db_host',
                                           unit, relid),
                "user": qutils.DB_USER,
                "password": utils.relation_get('quantum_password',
                                               unit, relid),
                "db": qutils.QUANTUM_DB
                }
            if None not in conf.itervalues():
                return conf
    return None


def get_nova_db_conf():
    for relid in utils.relation_ids('shared-db'):
        for unit in utils.relation_list(relid):
            conf = {
                "host": utils.relation_get('db_host',
                                           unit, relid),
                "user": qutils.NOVA_DB_USER,
                "password": utils.relation_get('nova_password',
                                               unit, relid),
                "db": qutils.NOVA_DB
                }
            if None not in conf.itervalues():
                return conf
    return None


def amqp_joined():
    utils.relation_set(username=qutils.RABBIT_USER,
                       vhost=qutils.RABBIT_VHOST)


@utils.inteli_restart(qutils.RESTART_MAP)
def amqp_changed():
    render_dhcp_agent_conf()
    render_quantum_conf()
    render_metadata_api_conf()


def get_rabbit_conf():
    for relid in utils.relation_ids('amqp'):
        for unit in utils.relation_list(relid):
            conf = {
                "rabbit_host": utils.relation_get('private-address',
                                                  unit, relid),
                "rabbit_virtual_host": qutils.RABBIT_VHOST,
                "rabbit_userid": qutils.RABBIT_USER,
                "rabbit_password": utils.relation_get('password',
                                                      unit, relid)
                }
            clustered = utils.relation_get('clustered', unit, relid)
            if clustered:
                conf['rabbit_host'] = utils.relation_get('vip', unit, relid)
            if None not in conf.itervalues():
                return conf
    return None


@utils.inteli_restart(qutils.RESTART_MAP)
def nm_changed():
    render_dhcp_agent_conf()
    render_l3_agent_conf()
    render_metadata_agent_conf()
    render_metadata_api_conf()
    render_evacuate_unit()
    store_ca_cert()


def store_ca_cert():
    ca_cert = get_ca_cert()
    if ca_cert:
        qutils.install_ca(ca_cert)


def get_ca_cert():
    for relid in utils.relation_ids('quantum-network-service'):
        for unit in utils.relation_list(relid):
            ca_cert = utils.relation_get('ca_cert', unit, relid)
            if ca_cert:
                return ca_cert
    return None


def cluster_departed():
    conf = get_keystone_conf()
    if conf and cluster.eligible_leader(None):
        qutils.reassign_agent_resources(conf)

utils.do_hooks({
    "install": install,
    "config-changed": config_changed,
    "upgrade-charm": upgrade_charm,
    "shared-db-relation-joined": db_joined,
    "shared-db-relation-changed": db_changed,
    "amqp-relation-joined": amqp_joined,
    "amqp-relation-changed": amqp_changed,
    "quantum-network-service-relation-changed": nm_changed,
    "cluster-relation-departed": cluster_departed
    })

sys.exit(0)
