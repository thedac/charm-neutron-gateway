import subprocess
import os
import uuid
import base64
import apt_pkg as apt
from random import randint
from lib.utils import (
    unit_get,
    juju_log as log
    )


OVS = "ovs"

OVS_PLUGIN = \
    "quantum.plugins.openvswitch.ovs_quantum_plugin.OVSQuantumPluginV2"
CORE_PLUGIN = {
    OVS: OVS_PLUGIN,
    }

OVS_PLUGIN_CONF = \
    "/etc/quantum/plugins/openvswitch/ovs_quantum_plugin.ini"
PLUGIN_CONF = {
    OVS: OVS_PLUGIN_CONF,
    }

GATEWAY_PKGS = {
    OVS: [
        "quantum-plugin-openvswitch-agent",
        "quantum-l3-agent",
        "quantum-dhcp-agent",
        'python-mysqldb',
        "nova-api-metadata"
        ],
    }

GATEWAY_AGENTS = {
    OVS: [
        "quantum-plugin-openvswitch-agent",
        "quantum-l3-agent",
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

RABBIT_USER = "nova"
RABBIT_VHOST = "nova"

INT_BRIDGE = "br-int"
EXT_BRIDGE = "br-ex"


def add_bridge(name):
    status = subprocess.check_output(["ovs-vsctl", "show"])
    if "Bridge {}".format(name) not in status:
        log('INFO', 'Creating bridge {}'.format(name))
        subprocess.check_call(["ovs-vsctl", "add-br", name])


def del_bridge(name):
    status = subprocess.check_output(["ovs-vsctl", "show"])
    if "Bridge {}".format(name) in status:
        log('INFO', 'Deleting bridge {}'.format(name))
        subprocess.check_call(["ovs-vsctl", "del-br", name])


def add_bridge_port(name, port):
    status = subprocess.check_output(["ovs-vsctl", "show"])
    if ("Bridge {}".format(name) in status and
        "Interface \"{}\"".format(port) not in status):
        log('INFO',
            'Adding port {} to bridge {}'.format(port, name))
        subprocess.check_call(["ovs-vsctl", "add-port", name, port])
        subprocess.check_call(["ip", "link", "set", port, "up"])


def del_bridge_port(name, port):
    status = subprocess.check_output(["ovs-vsctl", "show"])
    if ("Bridge {}".format(name) in status and
        "Interface \"{}\"".format(port) in status):
        log('INFO',
            'Deleting port {} from bridge {}'.format(port, name))
        subprocess.check_call(["ovs-vsctl", "del-port", name, port])
        subprocess.check_call(["ip", "link", "set", port, "down"])


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
            agent_cmd.append('--config-file=/etc/quantum/{}'\
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
            log('INFO', 'DHCP Agent %s down' % agent['id'])
            for network in \
                quantum.list_networks_on_dhcp_agent(agent['id'])['networks']:
                networks[network['id']] = agent['id']
        else:
            dhcp_agents.append(agent['id'])

    agents = quantum.list_agents(agent_type=L3_AGENT)
    routers = {}
    for agent in agents['agents']:
        if not agent['alive']:
            log('INFO', 'L3 Agent %s down' % agent['id'])
            for router in \
                quantum.list_routers_on_l3_agent(agent['id'])['routers']:
                routers[router['id']] = agent['id']
        else:
            l3_agents.append(agent['id'])

    index = 0
    for router_id in routers:
        agent = index % len(l3_agents)
        log('INFO',
            'Moving router %s from %s to %s' % \
            (router_id, routers[router_id], l3_agents[agent]))
        quantum.remove_router_from_l3_agent(l3_agent=routers[router_id],
                                            router_id=router_id)
        quantum.add_router_to_l3_agent(l3_agent=l3_agents[agent],
                                       body={'router_id': router_id})
        index += 1

    index = 0
    for network_id in networks:
        agent = index % len(dhcp_agents)
        log('INFO',
            'Moving network %s from %s to %s' % \
            (network_id, networks[network_id], dhcp_agents[agent]))
        quantum.remove_network_from_dhcp_agent(dhcp_agent=networks[network_id],
                                               network_id=network_id)
        quantum.add_network_to_dhcp_agent(dhcp_agent=dhcp_agents[agent],
                                          body={'network_id': network_id})
        index += 1
