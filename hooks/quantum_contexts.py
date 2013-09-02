# vim: set ts=4:et
import os
import uuid
import socket
from charmhelpers.core.hookenv import (
    config,
    relation_ids,
    related_units,
    relation_get,
    unit_get,
    cached,
)
from charmhelpers.fetch import (
    apt_install,
)
from charmhelpers.contrib.openstack.context import (
    OSContextGenerator,
    context_complete
)

DB_USER = "quantum"
QUANTUM_DB = "quantum"
NOVA_DB_USER = "nova"
NOVA_DB = "nova"

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


class NetworkServiceContext(OSContextGenerator):
    interfaces = ['quantum-network-service']

    def __call__(self):
        for rid in relation_ids('quantum-network-service'):
            for unit in related_units(rid):
                ctxt = {
                    'keystone_host': relation_get('keystone_host',
                                                  rid=rid, unit=unit),
                    'service_port': relation_get('service_port', rid=rid,
                                                 unit=unit),
                    'auth_port': relation_get('auth_port', rid=rid, unit=unit),
                    'service_tenant': relation_get('service_tenant',
                                                   rid=rid, unit=unit),
                    'service_username': relation_get('service_username',
                                                     rid=rid, unit=unit),
                    'service_password': relation_get('service_password',
                                                     rid=rid, unit=unit),
                    'quantum_host': relation_get('quantum_host',
                                                 rid=rid, unit=unit),
                    'quantum_port': relation_get('quantum_port',
                                                 rid=rid, unit=unit),
                    'quantum_url': relation_get('quantum_url',
                                                rid=rid, unit=unit),
                    'region': relation_get('region',
                                           rid=rid, unit=unit),
                    # XXX: Hard-coded http.
                    'service_protocol': 'http',
                    'auth_protocol': 'http',
                }
                if context_complete(ctxt):
                    return ctxt
        return {}


class ExternalPortContext(OSContextGenerator):
    def __call__(self):
        if config('ext-port'):
            return {"ext_port": config('ext-port')}
        else:
            return None


class QuantumGatewayContext(OSContextGenerator):
    def __call__(self):
        ctxt = {
            'shared_secret': get_shared_secret(),
            'local_ip': get_host_ip(),
            'core_plugin': CORE_PLUGIN[config('plugin')],
            'plugin': config('plugin')
        }
        return ctxt


class QuantumSharedDBContext(OSContextGenerator):
    interfaces = ['shared-db']

    def __call__(self):
        for rid in relation_ids('shared-db'):
            for unit in related_units(rid):
                ctxt = {
                    'database_host': relation_get('db_host', rid=rid,
                                                  unit=unit),
                    'quantum_database': QUANTUM_DB,
                    'quantum_user': DB_USER,
                    'quantum_password': relation_get('quantum_password',
                                                     rid=rid, unit=unit),
                    'nova_database': NOVA_DB,
                    'nova_user': NOVA_DB_USER,
                    'nova_password': relation_get('nova_password', rid=rid,
                                                  unit=unit)
                }
                if context_complete(ctxt):
                    return ctxt
        return {}


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
