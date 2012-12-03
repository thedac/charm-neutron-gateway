import subprocess
from utils import juju_log as log


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
        'python-mysqldb'
        ],
    NVP: [
        "quantum-plugin-nicira"
        ]
    }

GATEWAY_AGENTS = {
    OVS: [
        "quantum-plugin-openvswitch-agent",
        "quantum-l3-agent",
        "quantum-dhcp-agent"
        ]
    }

DB_USER = "quantum"
QUANTUM_DB = "quantum"
KEYSTONE_SERVICE = "quantum"

QUANTUM_CONF = "/etc/quantum/quantum.conf"
L3_AGENT_CONF = "/etc/quantum/l3_agent.ini"
DHCP_AGENT_CONF = "/etc/quantum/dhcp_agent.ini"

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
