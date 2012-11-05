
import subprocess

OVS_PLUGIN = \
    "quantum.plugins.openvswitch.ovs_quantum_plugin.OVSQuantumPluginV2"
NVP_PLUGIN = \
    "quantum.plugins.nicira.nicira_nvp_plugin.QuantumPlugin.NvpPluginV2"
CORE_PLUGIN = {
    "ovs": OVS_PLUGIN,
    "nvp": NVP_PLUGIN
    }

OVS_PLUGIN_CONF = \
    "/etc/quantum/plugins/openvswitch/ovs_quantum_plugin.ini"
NVP_PLUGIN_CONF = \
    "/etc/quantum/plugins/nicira/nvp.ini"
PLUGIN_CONF = {
    "ovs": OVS_PLUGIN_CONF,
    "nvp": NVP_PLUGIN_CONF
    }

DB_USER = "quantum"
QUANTUM_DB = "quantum"

QUANTUM_CONF = "/etc/quantum/quantum.conf"
L3_AGENT_CONF = "/etc/quantum/l3_agent.ini"
QUANTUM_API_CONF = "/etc/quantum/api-paste.ini"
DHCP_AGENT_CONF = "/etc/quantum/dhcp_agent.ini"

RABBIT_USER = "nova"
RABBIT_VHOST = "nova"


def add_bridge(name):
    status = subprocess.check_output(["ovs-vsctl", "show"])
    if "Bridge {}".format(name) not in status:
        subprocess.check_call(["ovs-vsctl", "add-br", name])


def del_bridge(name):
    status = subprocess.check_output(["ovs-vsctl", "show"])
    if "Bridge {}".format(name) in status:
        subprocess.check_call(["ovs-vsctl", "del-br", name])


def add_bridge_port(name, port):
    status = subprocess.check_output(["ovs-vsctl", "show"])
    if ("Bridge {}".format(name) in status and
        "Interface \"{}\"".format(port) not in status):
        subprocess.check_call(["ovs-vsctl", "add-port", name, port])


def del_bridge_port(name, port):
    status = subprocess.check_output(["ovs-vsctl", "show"])
    if ("Bridge {}".format(name) in status and
        "Interface \"{}\"".format(port) in status):
        subprocess.check_call(["ovs-vsctl", "del-port", name, port])
