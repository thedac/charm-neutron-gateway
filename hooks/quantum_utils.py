import subprocess
import os
import uuid
from utils import juju_log as log
from utils import get_os_version


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
        "quantum-plugin-nicira",
        "quantum-l3-agent",
        "quantum-dhcp-agent",
        'python-mysqldb',
        "nova-api-metadata"
        ]
    }

# TODO: conditionally add quantum-metadata-agent if
# running 2013.1 onwards. OR add some overrides
# start on starting quantum-l3-agent
# stop on stopping quantum-l3-agent
GATEWAY_AGENTS = {
    OVS: [
        "quantum-plugin-openvswitch-agent",
        "quantum-l3-agent",
        "quantum-dhcp-agent",
        "nova-api-metadata"
        ],
    NVP: [
        "quantum-l3-agent",
        "quantum-dhcp-agent",
        "nova-api-metadata"
        ]
    }

CLUSTERED_AGENTS = {
    OVS: [
        "quantum-l3-agent",
        "quantum-dhcp-agent",
        ],
    NVP: [
        "quantum-l3-agent",
        "quantum-dhcp-agent",
        ]
    }

STANDALONE_AGENTS = {
    OVS: [
        "quantum-plugin-openvswitch-agent",
        "nova-api-metadata"
        ],
    NVP: [
        "nova-api-metadata"
        ]
    }

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


def set_manager(manager):
    subprocess.check_call(["ovs-vsctl", "set-manager",
                           "ssl:%s".format(manager)])


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
