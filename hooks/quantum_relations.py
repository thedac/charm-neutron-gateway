#!/usr/bin/python

from charmhelpers.core.hookenv import (
    log, ERROR, WARNING,
    config,
    relation_ids,
    related_units,
    relation_get,
    relation_set,
    unit_get,
    Hooks, UnregisteredHookError
)
from charmhelpers.core.host import (
    apt_update,
    apt_install,
    restart_on_change
)
from charmhelpers.contrib.hahelpers.cluster_utils import(
    eligible_leader
)
from charmhelpers.contrib.openstack.openstack_utils import (
    configure_installation_source,
    get_os_codename_install_source,
    get_os_codename_package,
    get_os_version_codename
)
from charmhelpers.contrib.network.ovs import (
    add_bridge,
    add_bridge_port
)

from lib.utils import render_template, get_host_ip

import sys
import quantum_utils as qutils
import os

PLUGIN = config('plugin')
hooks = Hooks()


@hooks.hook()
def install():
    configure_installation_source(config('openstack-origin'))
    apt_update(fatal=True)
    if PLUGIN in qutils.GATEWAY_PKGS.keys():
        if PLUGIN in [qutils.OVS, qutils.NVP]:
            # Install OVS DKMS first to ensure that the ovs module
            # loaded supports GRE tunnels
            apt_install('openvswitch-datapath-dkms', fatal=True)
        apt_install(qutils.GATEWAY_PKGS[PLUGIN], fatal=True)
    else:
        log('Please provide a valid plugin config', level=ERROR)
        sys.exit(1)


@hooks.hook()
@restart_on_change(qutils.RESTART_MAP[PLUGIN])
def config_changed():
    src = config('openstack-origin')
    available = get_os_codename_install_source(src)
    installed = get_os_codename_package('quantum-common')
    if (available and
            get_os_version_codename(available) >
            get_os_version_codename(installed)):
        qutils.do_openstack_upgrade()

    if PLUGIN in qutils.GATEWAY_PKGS.keys():
        render_quantum_conf()
        render_dhcp_agent_conf()
        render_l3_agent_conf()
        render_metadata_agent_conf()
        render_metadata_api_conf()
        render_plugin_conf()
        render_ext_port_upstart()
        render_evacuate_unit()
        if PLUGIN in [qutils.OVS, qutils.NVP]:
            add_bridge(qutils.INT_BRIDGE)
            add_bridge(qutils.EXT_BRIDGE)
            ext_port = config('ext-port')
            if ext_port:
                add_bridge_port(qutils.EXT_BRIDGE, ext_port)
    else:
        log('Please provide a valid plugin config', level=ERROR)
        sys.exit(1)


@hooks.hook()
def upgrade_charm():
    install()
    config_changed()


def render_ext_port_upstart():
    if config('ext-port'):
        with open(qutils.EXT_PORT_CONF, "w") as conf:
            conf.write(
                render_template(os.path.basename(qutils.EXT_PORT_CONF),
                                {"ext_port": config('ext-port')})
            )
    else:
        if os.path.exists(qutils.EXT_PORT_CONF):
            os.remove(qutils.EXT_PORT_CONF)


def render_l3_agent_conf():
    context = get_keystone_conf()
    if (context and
            os.path.exists(qutils.L3_AGENT_CONF)):
        with open(qutils.L3_AGENT_CONF, "w") as conf:
            conf.write(
                render_template(os.path.basename(qutils.L3_AGENT_CONF),
                                context)
            )


def render_dhcp_agent_conf():
    if (os.path.exists(qutils.DHCP_AGENT_CONF)):
        with open(qutils.DHCP_AGENT_CONF, "w") as conf:
            conf.write(
                render_template(os.path.basename(qutils.DHCP_AGENT_CONF),
                                {"plugin": PLUGIN})
            )


def render_metadata_agent_conf():
    context = get_keystone_conf()
    if (context and
            os.path.exists(qutils.METADATA_AGENT_CONF)):
        context['local_ip'] = get_host_ip()
        context['shared_secret'] = qutils.get_shared_secret()
        with open(qutils.METADATA_AGENT_CONF, "w") as conf:
            conf.write(
                render_template(os.path.basename(qutils.METADATA_AGENT_CONF),
                                context)
            )


def render_quantum_conf():
    context = get_rabbit_conf()
    if (context and
            os.path.exists(qutils.QUANTUM_CONF)):
        context['core_plugin'] = \
            qutils.CORE_PLUGIN[PLUGIN]
        with open(qutils.QUANTUM_CONF, "w") as conf:
            conf.write(
                render_template(os.path.basename(qutils.QUANTUM_CONF),
                                context)
            )


def render_plugin_conf():
    context = get_quantum_db_conf()
    if (context and
            os.path.exists(qutils.PLUGIN_CONF[PLUGIN])):
        context['local_ip'] = get_host_ip()
        conf_file = qutils.PLUGIN_CONF[PLUGIN]
        with open(conf_file, "w") as conf:
            conf.write(
                render_template(os.path.basename(conf_file),
                                context)
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
            conf.write(
                render_template(os.path.basename(qutils.NOVA_CONF),
                                context)
            )


def render_evacuate_unit():
    context = get_keystone_conf()
    if context:
        with open('/usr/local/bin/quantum-evacuate-unit', "w") as conf:
            conf.write(render_template('evacuate_unit.py', context))
        os.chmod('/usr/local/bin/quantum-evacuate-unit', 0700)


def get_keystone_conf():
    for relid in relation_ids('quantum-network-service'):
        for unit in related_units(relid):
            conf = {
                "keystone_host": relation_get('keystone_host',
                                              unit, relid),
                "service_port": relation_get('service_port',
                                             unit, relid),
                "auth_port": relation_get('auth_port', unit, relid),
                "service_username": relation_get('service_username',
                                                 unit, relid),
                "service_password": relation_get('service_password',
                                                 unit, relid),
                "service_tenant": relation_get('service_tenant',
                                               unit, relid),
                "quantum_host": relation_get('quantum_host',
                                             unit, relid),
                "quantum_port": relation_get('quantum_port',
                                             unit, relid),
                "quantum_url": relation_get('quantum_url',
                                            unit, relid),
                "region": relation_get('region',
                                       unit, relid)
            }
            if None not in conf.itervalues():
                return conf
    return None


@hooks.hook('shared-db-relation-joined')
def db_joined():
    relation_set(quantum_username=qutils.DB_USER,
                 quantum_database=qutils.QUANTUM_DB,
                 quantum_hostname=unit_get('private-address'),
                 nova_username=qutils.NOVA_DB_USER,
                 nova_database=qutils.NOVA_DB,
                 nova_hostname=unit_get('private-address'))


@hooks.hook('shared-db-relation-changed')
@restart_on_change(qutils.RESTART_MAP[PLUGIN])
def db_changed():
    render_plugin_conf()
    render_metadata_api_conf()


def get_quantum_db_conf():
    for relid in relation_ids('shared-db'):
        for unit in related_units(relid):
            conf = {
                "host": relation_get('db_host',
                                     unit, relid),
                "user": qutils.DB_USER,
                "password": relation_get('quantum_password',
                                         unit, relid),
                "db": qutils.QUANTUM_DB
            }
            if None not in conf.itervalues():
                return conf
    return None


def get_nova_db_conf():
    for relid in relation_ids('shared-db'):
        for unit in related_units(relid):
            conf = {
                "host": relation_get('db_host',
                                     unit, relid),
                "user": qutils.NOVA_DB_USER,
                "password": relation_get('nova_password',
                                         unit, relid),
                "db": qutils.NOVA_DB
            }
            if None not in conf.itervalues():
                return conf
    return None


@hooks.hook('amqp-relation-joined')
def amqp_joined():
    relation_set(username=qutils.RABBIT_USER,
                 vhost=qutils.RABBIT_VHOST)


@hooks.hook('amqp-relation-changed')
@restart_on_change(qutils.RESTART_MAP[PLUGIN])
def amqp_changed():
    render_dhcp_agent_conf()
    render_quantum_conf()
    render_metadata_api_conf()


def get_rabbit_conf():
    for relid in relation_ids('amqp'):
        for unit in related_units(relid):
            conf = {
                "rabbit_host": relation_get('private-address',
                                            unit, relid),
                "rabbit_virtual_host": qutils.RABBIT_VHOST,
                "rabbit_userid": qutils.RABBIT_USER,
                "rabbit_password": relation_get('password',
                                                unit, relid)
            }
            clustered = relation_get('clustered', unit, relid)
            if clustered:
                conf['rabbit_host'] = relation_get('vip', unit, relid)
            if None not in conf.itervalues():
                return conf
    return None


@hooks.hook('quantum-network-service-relation-changed')
@restart_on_change(qutils.RESTART_MAP[PLUGIN])
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
    for relid in relation_ids('quantum-network-service'):
        for unit in related_units(relid):
            ca_cert = relation_get('ca_cert', unit, relid)
            if ca_cert:
                return ca_cert
    return None


@hooks.hook("cluster-relation-departed")
def cluster_departed():
    if PLUGIN == 'nvp':
        log('Unable to re-assign agent resources for failed nodes with nvp',
            level=WARNING)
        return
    conf = get_keystone_conf()
    if conf and eligible_leader(None):
        qutils.reassign_agent_resources(conf)


if __name__ == '__main__':
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        log('Unknown hook {} - skipping.'.format(e))
