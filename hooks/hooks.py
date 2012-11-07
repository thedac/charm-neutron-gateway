#!/usr/bin/python

import utils
import sys
import quantum_utils as qutils
import os

PLUGIN = utils.config_get('plugin')


def install():
    utils.configure_source()
    # TODO: when using the nicira plugin /etc/default/quantum-server
    # will also need to be updated to point to the correct configuration
    if PLUGIN in qutils.PLUGIN_PKGS.keys():
        if PLUGIN == "ovs":
            # Install OVS DKMS first to ensure that the ovs module
            # loaded supports GRE tunnels
            utils.install('openvswitch-datapath-dkms')
        utils.install('quantum-server',
                      'python-mysqldb',
                      *qutils.PLUGIN_PKGS[PLUGIN])
    else:
        utils.juju_log('ERROR', 'Please provide a valid plugin config')
        sys.exit(1)


def config_changed():
    if PLUGIN in qutils.PLUGIN_PKGS.keys():
        render_api_paste_conf()
        render_quantum_conf()
        render_plugin_conf()
        render_l3_agent_conf()
        if PLUGIN == "ovs":
            qutils.add_bridge('br-int')
            qutils.add_bridge('br-ex')
            ext_port = utils.config_get('ext-port')
            if ext_port:
                qutils.add_bridge_port('br-ex', ext_port)
        utils.restart(*(qutils.PLUGIN_AGENT[PLUGIN] + \
                        qutils.GATEWAY_AGENTS[PLUGIN]))
    else:
        utils.juju_log('ERROR',
                       'Please provide a valid plugin config')
        sys.exit(1)

    configure_networking()


def configure_networking():
    keystone_conf = get_keystone_conf()
    db_conf = get_db_conf()
    if (utils.config_get('conf-ext-net') and
        keystone_conf and
        db_conf):
        qutils.configure_ext_net(
                 username=keystone_conf['service_username'],
                 password=keystone_conf['service_password'],
                 tenant=keystone_conf['service_tenant'],
                 url="http://{}:{}/v2.0/".format(
                        keystone_conf['keystone_host'],
                        keystone_conf['auth_port']
                        ),
                 ext_net_name=utils.config_get('ext-net-name'),
                 gateway_ip=utils.config_get('ext-gw-ip'),
                 default_gateway=utils.config_get('ext-net-gateway'),
                 cidr=utils.config_get('ext-net-cidr'),
                 start_floating_ip=utils.config_get('pool-floating-start'),
                 end_floating_ip=utils.config_get('pool-floating-end')
            )


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


def render_api_paste_conf():
    context = get_keystone_conf()
    if (context and
        os.path.exists(qutils.QUANTUM_API_CONF)):
        with open(qutils.QUANTUM_API_CONF, "w") as conf:
            conf.write(utils.render_template(
                            os.path.basename(qutils.QUANTUM_API_CONF),
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


def keystone_joined():
    url = "http://{}:9696/".format(utils.unit_get('private-address'))
    utils.relation_set(service=qutils.KEYSTONE_SERVICE,
                       region=utils.config_get('region'),
                       public_url=url,
                       admin_url=url,
                       internal_url=url)


def keystone_changed():
    render_l3_agent_conf()
    render_api_paste_conf()
    utils.restart(*qutils.GATEWAY_AGENTS[PLUGIN])
    notify_agents()
    configure_networking()


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
    utils.relation_set(username=qutils.DB_USER,
                       database=qutils.QUANTUM_DB,
                       hostname=utils.unit_get('private-address'))


def db_changed():
    render_plugin_conf()
    utils.restart(*(qutils.GATEWAY_AGENTS[PLUGIN] + \
                    qutils.PLUGIN_AGENT[PLUGIN]))
    configure_networking()


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
    utils.restart(*(qutils.GATEWAY_AGENTS[PLUGIN] + \
                    qutils.PLUGIN_AGENT[PLUGIN]))


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


def nm_joined():
    keystone_conf = get_keystone_conf()
    if keystone_conf:
        utils.relation_set(**keystone_conf)  # IGNORE:W0142
    utils.relation_set(plugin=PLUGIN)


def notify_agents():
    keystone_conf = get_keystone_conf()
    if keystone_conf:
        for relid in utils.relation_ids('network-manager'):
            utils.relation_set(relid=relid,
                               plugin=PLUGIN,
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
