import subprocess
import os
import uuid
import base64
import apt_pkg as apt
from charmhelpers.core.hookenv import (
    log,
    config
)
from charmhelpers.core.host import (
    apt_install
)
from charmhelpers.contrib.openstack.openstack_utils import (
    configure_installation_source
)

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

GATEWAY_AGENTS = {
    OVS: [
        "quantum-plugin-openvswitch-agent",
        "quantum-l3-agent",
        "quantum-dhcp-agent",
        "nova-api-metadata"
    ],
    NVP: [
        "quantum-dhcp-agent",
        "nova-api-metadata"
    ],
}

EXT_PORT_CONF = '/etc/init/ext-port.conf'


def get_os_version(package=None):
    apt.init()
    cache = apt.Cache()
    pkg = cache[package or 'quantum-common']
    if pkg.current_ver:
        return apt.upstream_version(pkg.current_ver.ver_str)
    else:
        return None


if get_os_version('quantum-common') >= "2013.1":
    for plugin in GATEWAY_AGENTS:
        GATEWAY_AGENTS[plugin].append("quantum-metadata-agent")

DB_USER = "quantum"
QUANTUM_DB = "quantum"
KEYSTONE_SERVICE = "quantum"
NOVA_DB_USER = "nova"
NOVA_DB = "nova"

QUANTUM_CONF = "/etc/quantum/quantum.conf"
L3_AGENT_CONF = "/etc/quantum/l3_agent.ini"
DHCP_AGENT_CONF = "/etc/quantum/dhcp_agent.ini"
METADATA_AGENT_CONF = "/etc/quantum/metadata_agent.ini"
NOVA_CONF = "/etc/nova/nova.conf"


OVS_RESTART_MAP = {
    QUANTUM_CONF: [
        'quantum-l3-agent',
        'quantum-dhcp-agent',
        'quantum-metadata-agent',
        'quantum-plugin-openvswitch-agent'
    ],
    DHCP_AGENT_CONF: [
        'quantum-dhcp-agent'
    ],
    L3_AGENT_CONF: [
        'quantum-l3-agent'
    ],
    METADATA_AGENT_CONF: [
        'quantum-metadata-agent'
    ],
    OVS_PLUGIN_CONF: [
        'quantum-plugin-openvswitch-agent'
    ],
    NOVA_CONF: [
        'nova-api-metadata'
    ]
}

NVP_RESTART_MAP = {
    QUANTUM_CONF: [
        'quantum-dhcp-agent',
        'quantum-metadata-agent'
    ],
    DHCP_AGENT_CONF: [
        'quantum-dhcp-agent'
    ],
    METADATA_AGENT_CONF: [
        'quantum-metadata-agent'
    ],
    NOVA_CONF: [
        'nova-api-metadata'
    ]
}


RESTART_MAP = {
    OVS: OVS_RESTART_MAP,
    NVP: NVP_RESTART_MAP
}


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


def flush_local_configuration():
    if os.path.exists('/usr/bin/quantum-netns-cleanup'):
        cmd = [
            "quantum-netns-cleanup",
            "--config-file=/etc/quantum/quantum.conf"
        ]
        for agent_conf in ['l3_agent.ini', 'dhcp_agent.ini']:
            agent_cmd = list(cmd)
            agent_cmd.append('--config-file=/etc/quantum/{}'
                             .format(agent_conf))
            subprocess.call(agent_cmd)


def install_ca(ca_cert):
    with open('/usr/local/share/ca-certificates/keystone_juju_ca_cert.crt',
              'w') as crt:
        crt.write(base64.b64decode(ca_cert))
    subprocess.check_call(['update-ca-certificates', '--fresh'])

DHCP_AGENT = "DHCP Agent"
L3_AGENT = "L3 Agent"


def reassign_agent_resources(env):
    ''' Use agent scheduler API to detect down agents and re-schedule '''
    from quantumclient.v2_0 import client
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


def do_openstack_upgrade():
    configure_installation_source(config('openstack-origin'))
    plugin = config('plugin')
    pkgs = []
    if plugin in GATEWAY_PKGS.keys():
        pkgs.extend(GATEWAY_PKGS[plugin])
        if plugin in [OVS, NVP]:
            pkgs.append('openvswitch-datapath-dkms')
    dpkg_opts = [
        '--option', 'Dpkg::Options::=--force-confold',
        '--option', 'Dpkg::Options::=--force-confdef'
    ]
    apt_install(pkgs, options=dpkg_opts, fatal=True)
