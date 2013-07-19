import os
import uuid
import socket
from charmhelpers.core.hookenv import (
    log,
    config,
    unit_get,
    cached
)
from charmhelpers.core.host import (
    apt_install,
    apt_update
)
from charmhelpers.contrib.network.ovs import (
    add_bridge,
    add_bridge_port
)
from charmhelpers.contrib.openstack.utils import (
    configure_installation_source,
    get_os_codename_package,
    get_os_codename_install_source
)
import charmhelpers.contrib.openstack.context as context
import charmhelpers.contrib.openstack.templating as templating
import quantum_contexts
from collections import OrderedDict

OVS = "ovs"
NVP = "nvp"

OVS_PLUGIN = \
    "quantum.plugins.openvswitch.ovs_quantum_plugin.OVSQuantumPluginV2"
NVP_PLUGIN = \
    "quantum.plugins.nicira.nicira_nvp_plugin.QuantumPlugin.NvpPluginV2"
CORE_PLUGIN = {
    OVS: OVS_PLUGIN,
    NVP: NVP_PLUGIN
}


def valid_plugin():
    return config('plugin') in CORE_PLUGIN

OVS_PLUGIN_CONF = \
    "/etc/quantum/plugins/openvswitch/ovs_quantum_plugin.ini"
NVP_PLUGIN_CONF = \
    "/etc/quantum/plugins/nicira/nvp.ini"
PLUGIN_CONF = {
    OVS: OVS_PLUGIN_CONF,
    NVP: NVP_PLUGIN_CONF
}

GATEWAY_PKGS = {
    OVS: [
        "quantum-plugin-openvswitch-agent",
        "quantum-l3-agent",
        "quantum-dhcp-agent",
        'python-mysqldb',
        "nova-api-metadata"
    ],
    NVP: [
        "openvswitch-switch",
        "quantum-dhcp-agent",
        'python-mysqldb',
        "nova-api-metadata"
    ]
}

EARLY_PACKAGES = {
    OVS: ['openvswitch-datapath-dkms']
}


def get_early_packages():
    '''Return a list of package for pre-install based on configured plugin'''
    if config('plugin') in EARLY_PACKAGES:
        return EARLY_PACKAGES[config('plugin')]
    else:
        return []


def get_packages():
    '''Return a list of packages for install based on the configured plugin'''
    return GATEWAY_PKGS[config('plugin')]

EXT_PORT_CONF = '/etc/init/ext-port.conf'
TEMPLATES = 'templates'

QUANTUM_CONF = "/etc/quantum/quantum.conf"
L3_AGENT_CONF = "/etc/quantum/l3_agent.ini"
DHCP_AGENT_CONF = "/etc/quantum/dhcp_agent.ini"
METADATA_AGENT_CONF = "/etc/quantum/metadata_agent.ini"
NOVA_CONF = "/etc/nova/nova.conf"

SHARED_CONFIG_FILES = {
    DHCP_AGENT_CONF: {
        'hook_contexts': [quantum_contexts.QuantumGatewayContext()],
        'services': ['quantum-dhcp-agent']
    },
    METADATA_AGENT_CONF: {
        'hook_contexts': [quantum_contexts.NetworkServiceContext()],
        'services': ['quantum-metadata-agent']
    },
    NOVA_CONF: {
        'hook_contexts': [context.AMQPContext(),
                          context.SharedDBContext(),
                          quantum_contexts.NetworkServiceContext(),
                          quantum_contexts.QuantumGatewayContext()],
        'services': ['nova-api-metadata']
    },
}

OVS_CONFIG_FILES = {
    QUANTUM_CONF: {
        'hook_contexts': [context.AMQPContext(),
                          quantum_contexts.QuantumGatewayContext()],
        'services': ['quantum-l3-agent',
                     'quantum-dhcp-agent',
                     'quantum-metadata-agent',
                     'quantum-plugin-openvswitch-agent']
    },
    L3_AGENT_CONF: {
        'hook_contexts': [quantum_contexts.NetworkServiceContext()],
        'services': ['quantum-l3-agent']
    },
    # TODO: Check to see if this is actually required
    OVS_PLUGIN_CONF: {
        'hook_contexts': [context.SharedDBContext(),
                          quantum_contexts.QuantumGatewayContext()],
        'services': ['quantum-plugin-openvswitch-agent']
    },
    EXT_PORT_CONF: {
        'hook_contexts': [quantum_contexts.ExternalPortContext()],
        'services': []
    }
}

NVP_CONFIG_FILES = {
    QUANTUM_CONF: {
        'hook_contexts': [context.AMQPContext()],
        'services': ['quantum-dhcp-agent', 'quantum-metadata-agent']
    },
}

CONFIG_FILES = {
    NVP: NVP_CONFIG_FILES.update(SHARED_CONFIG_FILES),
    OVS: OVS_CONFIG_FILES.update(SHARED_CONFIG_FILES),
}


def register_configs():
    ''' Register config files with their respective contexts. '''
    release = get_os_codename_package('quantum-common', fatal=False) or \
        'essex'
    configs = templating.OSConfigRenderer(templates_dir=TEMPLATES,
                                          openstack_release=release)

    plugin = config('plugin')
    for conf in CONFIG_FILES[plugin]:
        configs.register(conf, CONFIG_FILES[conf]['hook_contexts'])

    return configs


def restart_map():
    '''
    Determine the correct resource map to be passed to
    charmhelpers.core.restart_on_change() based on the services configured.

    :returns: dict: A dictionary mapping config file to lists of services
                    that should be restarted when file changes.
    '''
    _map = []
    for f, ctxt in CONFIG_FILES[config('plugin')].iteritems():
        svcs = []
        for svc in ctxt['services']:
            svcs.append(svc)
        if svcs:
            _map.append((f, svcs))
    return OrderedDict(_map)


DB_USER = "quantum"
QUANTUM_DB = "quantum"
KEYSTONE_SERVICE = "quantum"
NOVA_DB_USER = "nova"
NOVA_DB = "nova"

RABBIT_USER = "nova"
RABBIT_VHOST = "nova"

INT_BRIDGE = "br-int"
EXT_BRIDGE = "br-ex"

SHARED_SECRET = "/etc/quantum/secret.txt"


def get_shared_secret():
    secret = None
    if not os.path.exists(SHARED_SECRET):
        secret = str(uuid.uuid4())
        with open(SHARED_SECRET, 'w') as secret_file:
            secret_file.write(secret)
    else:
        with open(SHARED_SECRET, 'r') as secret_file:
            secret = secret_file.read().strip()
    return secret

DHCP_AGENT = "DHCP Agent"
L3_AGENT = "L3 Agent"


def reassign_agent_resources():
    ''' Use agent scheduler API to detect down agents and re-schedule '''
    env = quantum_contexts.NetworkServiceContext()()
    if not env:
        log('Unable to re-assign resources at this time')
        return
    try:
        from quantumclient.v2_0 import client
    except ImportError:
        ''' Try to import neutronclient instead for havana+ '''
        from neutronclient.v2_0 import client

    # TODO: Fixup for https keystone
    auth_url = 'http://%(keystone_host)s:%(auth_port)s/v2.0' % env
    quantum = client.Client(username=env['service_username'],
                            password=env['service_password'],
                            tenant_name=env['service_tenant'],
                            auth_url=auth_url,
                            region_name=env['region'])

    agents = quantum.list_agents(agent_type=DHCP_AGENT)
    dhcp_agents = []
    l3_agents = []
    networks = {}
    for agent in agents['agents']:
        if not agent['alive']:
            log('DHCP Agent %s down' % agent['id'])
            for network in \
                quantum.list_networks_on_dhcp_agent(agent['id'])['networks']:
                networks[network['id']] = agent['id']
        else:
            dhcp_agents.append(agent['id'])

    agents = quantum.list_agents(agent_type=L3_AGENT)
    routers = {}
    for agent in agents['agents']:
        if not agent['alive']:
            log('L3 Agent %s down' % agent['id'])
            for router in \
                quantum.list_routers_on_l3_agent(agent['id'])['routers']:
                routers[router['id']] = agent['id']
        else:
            l3_agents.append(agent['id'])

    index = 0
    for router_id in routers:
        agent = index % len(l3_agents)
        log('Moving router %s from %s to %s' %
            (router_id, routers[router_id], l3_agents[agent]))
        quantum.remove_router_from_l3_agent(l3_agent=routers[router_id],
                                            router_id=router_id)
        quantum.add_router_to_l3_agent(l3_agent=l3_agents[agent],
                                       body={'router_id': router_id})
        index += 1

    index = 0
    for network_id in networks:
        agent = index % len(dhcp_agents)
        log('Moving network %s from %s to %s' %
            (network_id, networks[network_id], dhcp_agents[agent]))
        quantum.remove_network_from_dhcp_agent(dhcp_agent=networks[network_id],
                                               network_id=network_id)
        quantum.add_network_to_dhcp_agent(dhcp_agent=dhcp_agents[agent],
                                          body={'network_id': network_id})
        index += 1


def do_openstack_upgrade(configs):
    """
    Perform an upgrade.  Takes care of upgrading packages, rewriting
    configs, database migrations and potentially any other post-upgrade
    actions.

    :param configs: The charms main OSConfigRenderer object.
    """
    new_src = config('openstack-origin')
    new_os_rel = get_os_codename_install_source(new_src)

    log('Performing OpenStack upgrade to %s.' % (new_os_rel))

    configure_installation_source(new_src)
    dpkg_opts = [
        '--option', 'Dpkg::Options::=--force-confnew',
        '--option', 'Dpkg::Options::=--force-confdef',
    ]
    apt_update(fatal=True)
    apt_install(packages=GATEWAY_PKGS[config('plugin')], options=dpkg_opts,
                fatal=True)

    # set CONFIGS to load templates from new release
    configs.set_release(openstack_release=new_os_rel)


@cached
def get_host_ip(hostname=None):
    try:
        import dns.resolver
    except ImportError:
        apt_install('python-dnspython', fatal=True)
        import dns.resolver
    hostname = hostname or unit_get('private-address')
    try:
        # Test to see if already an IPv4 address
        socket.inet_aton(hostname)
        return hostname
    except socket.error:
        answers = dns.resolver.query(hostname, 'A')
        if answers:
            return answers[0].address


def configure_ovs():
    if config('plugin') == OVS:
        add_bridge(INT_BRIDGE)
        add_bridge(EXT_BRIDGE)
        ext_port = config('ext-port')
        if ext_port:
            add_bridge_port(EXT_BRIDGE, ext_port)
    if config('plugin') == NVP:
        add_bridge(INT_BRIDGE)
