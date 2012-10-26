
import utils
import subprocess
import os

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

MYSQL_CS = "mysql://%(user)s:%(password)s@%(host)s/%(db)s?charset=utf8"


def update_config_block(block, conf, **kwargs):
    """
    Updates configuration file blocks given kwargs.
    Can be used to update driver settings for a particular backend,
    setting the sql connection, etc.

    Parses block heading as '[block]'

    If block does not exist, a new block will be created at end of file with
    given kwargs
    """
    f = open(conf, "r+")
    orig = f.readlines()
    new = []
    heading = "[{}]\n".format(block)

    lines = len(orig)
    ln = 0

    def update_block(block):
        for k, v in kwargs.iteritems():
            for l in block:
                if l.strip().split(" ")[0] == k:
                    block[block.index(l)] = "{} = {}\n".format(k, v)
                    return
            block.append('{} = {}\n'.format(k, v))
            block.append('\n')

    found = False
    while ln < lines:
        if orig[ln] != heading:
            new.append(orig[ln])
            ln += 1
        else:
            new.append(orig[ln])
            ln += 1
            block = []
            while orig[ln].strip() != '':
                block.append(orig[ln])
                ln += 1
            update_block(block)
            new += block
            found = True

    if not found:
        if new[(len(new) - 1)].strip() != '':
            new.append('\n')
        new.append('{}'.format(heading))
        for k, v in kwargs.iteritems():
            new.append('{} = {}\n'.format(k, v))
        new.append('\n')

    # backup original config
    backup = open(conf + '.juju-back', 'w+')
    for l in orig:
        backup.write(l)
    backup.close()

    # update config
    f.seek(0)
    f.truncate()
    for l in new:
        f.write(l)


def configure_core_plugin(plugin):
    update_config_block("DEFAULT", QUANTUM_CONF,
                        core_plugin=CORE_PLUGIN[plugin])


def configure_db_connection(plugin, host, password):
    update_config_block(
        "DATABASE", PLUGIN_CONF[plugin],
        sql_connection=MYSQL_CS.format(host=host,
                                       user=DB_USER,
                                       password=password,
                                       db=QUANTUM_DB)
        )


def configure_local_ip(plugin, address):
    update_config_block("OVS", PLUGIN_CONF[plugin], local_ip=address)


def configure_keystone(keystone_host,
                       token,
                       service_port,
                       auth_port,
                       username,
                       password,
                       tenant):
    if os.path.exists(L3_AGENT_CONF):  # Indicated OVS model is in use.
        update_config_block("DEFAULT", L3_AGENT_CONF,
                            auth_url="http://{}:{}/v2.0".format(keystone_host,
                                                                auth_port),
                            auth_region="RegionOne",
                            admin_tenant_name=tenant,
                            admin_user=username,
                            admin_password=password)
    update_config_block("filter:authtoken", QUANTUM_API_CONF,
                        auth_host=keystone_host,
                        auth_port=auth_port,
                        admin_tenant_name=tenant,
                        admin_user=username,
                        admin_password=password)


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
    if "Bridge {}".format(name) in status:
        subprocess.check_call(["ovs-vsctl", "add-port", name, port])


def del_bridge_port(name, port):
    status = subprocess.check_output(["ovs-vsctl", "show"])
    if ("Bridge {}".format(name) in status and
        "Interface \"{}\"".format(port) in status):
        subprocess.check_call(["ovs-vsctl", "del-port", name, port])
