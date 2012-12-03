#!/usr/bin/python

import utils
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


def config_changed():
    if PLUGIN in qutils.GATEWAY_PKGS.keys():
        render_quantum_conf()
        render_plugin_conf()
        render_l3_agent_conf()
        if PLUGIN == qutils.OVS:
            qutils.add_bridge(qutils.INT_BRIDGE)
            qutils.add_bridge(qutils.EXT_BRIDGE)
            ext_port = utils.config_get('ext-port')
            if ext_port:
                qutils.add_bridge_port(qutils.EXT_BRIDGE, ext_port)
        utils.restart(*qutils.GATEWAY_AGENTS[PLUGIN])
    else:
        utils.juju_log('ERROR',
                       'Please provide a valid plugin config')
        sys.exit(1)


def upgrade_charm():
    install()
    config_changed()


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
    context = get_db_conf()
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
                                                     unit, relid)
                }
            if None not in conf.itervalues():
                return conf
    return None


def db_joined():
    utils.relation_set(username=qutils.DB_USER,
                       database=qutils.QUANTUM_DB,
                       hostname=utils.unit_get('private-address'))


def db_changed():
    render_plugin_conf()
    utils.restart(*qutils.GATEWAY_AGENTS[PLUGIN])


def get_db_conf():
    for relid in utils.relation_ids('shared-db'):
        for unit in utils.relation_list(relid):
            conf = {
                "host": utils.relation_get('private-address',
                                           unit, relid),
                "user": qutils.DB_USER,
                "password": utils.relation_get('password',
                                               unit, relid),
                "db": qutils.QUANTUM_DB
                }
            if None not in conf.itervalues():
                return conf
    return None


def amqp_joined():
    utils.relation_set(username=qutils.RABBIT_USER,
                       vhost=qutils.RABBIT_VHOST)


def amqp_changed():
    render_quantum_conf()
    utils.restart(*qutils.GATEWAY_AGENTS[PLUGIN])


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
            if None not in conf.itervalues():
                return conf
    return None


def nm_changed():
    render_l3_agent_conf()
    utils.restart(*qutils.GATEWAY_AGENTS[PLUGIN])


utils.do_hooks({
    "install": install,
    "config-changed": config_changed,
    "upgrade-charm": upgrade_charm,
    "shared-db-relation-joined": db_joined,
    "shared-db-relation-changed": db_changed,
    "amqp-relation-joined": amqp_joined,
    "amqp-relation-changed": amqp_changed,
    "quantum-network-service-relation-changed": nm_changed,
    })

sys.exit(0)
