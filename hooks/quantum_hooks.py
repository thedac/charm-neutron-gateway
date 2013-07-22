#!/usr/bin/python

from charmhelpers.core.hookenv import (
    log, ERROR, WARNING,
    config,
    relation_get,
    relation_set,
    unit_get,
    Hooks, UnregisteredHookError
)
from charmhelpers.core.host import (
    apt_update,
    apt_install,
    filter_installed_packages,
    restart_on_change
)
from charmhelpers.contrib.hahelpers.cluster import(
    eligible_leader
)
from charmhelpers.contrib.hahelpers.apache import(
    install_ca_cert
)
from charmhelpers.contrib.openstack.utils import (
    configure_installation_source,
    openstack_upgrade_available
)

import sys
from quantum_utils import (
    register_configs,
    restart_map,
    do_openstack_upgrade,
    get_packages,
    get_early_packages,
    valid_plugin,
    configure_ovs,
    reassign_agent_resources,
)
from quantum_contexts import (
    DB_USER, QUANTUM_DB,
    NOVA_DB_USER, NOVA_DB,
)

hooks = Hooks()
CONFIGS = register_configs()


@hooks.hook('install')
def install():
    configure_installation_source(config('openstack-origin'))
    apt_update(fatal=True)
    if valid_plugin():
        apt_install(filter_installed_packages(get_early_packages()),
                    fatal=True)
        apt_install(filter_installed_packages(get_packages()),
                    fatal=True)
    else:
        log('Please provide a valid plugin config', level=ERROR)
        sys.exit(1)


@hooks.hook('config-changed')
@restart_on_change(restart_map())
def config_changed():
    if openstack_upgrade_available('quantum-common'):
        do_openstack_upgrade(CONFIGS)
    if valid_plugin():
        CONFIGS.write_all()
        configure_ovs()
    else:
        log('Please provide a valid plugin config', level=ERROR)
        sys.exit(1)


@hooks.hook('upgrade-charm')
def upgrade_charm():
    install()
    config_changed()


@hooks.hook('shared-db-relation-joined')
def db_joined():
    relation_set(quantum_username=DB_USER,
                 quantum_database=QUANTUM_DB,
                 quantum_hostname=unit_get('private-address'),
                 nova_username=NOVA_DB_USER,
                 nova_database=NOVA_DB,
                 nova_hostname=unit_get('private-address'))


@hooks.hook('amqp-relation-joined')
def amqp_joined():
    relation_set(username=config('rabbit-user'),
                 vhost=config('rabbit-vhost'))


@hooks.hook('shared-db-relation-changed',
            'amqp-relation-changed')
@restart_on_change(restart_map())
def db_amqp_changed():
    CONFIGS.write_all()


@hooks.hook('quantum-network-service-relation-changed')
@restart_on_change(restart_map())
def nm_changed():
    CONFIGS.write_all()
    if relation_get('ca_cert'):
        install_ca_cert(relation_get('ca_cert'))


@hooks.hook("cluster-relation-departed")
def cluster_departed():
    if config('plugin') == 'nvp':
        log('Unable to re-assign agent resources for failed nodes with nvp',
            level=WARNING)
        return
    if eligible_leader(None):
        reassign_agent_resources()


if __name__ == '__main__':
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        log('Unknown hook {} - skipping.'.format(e))
