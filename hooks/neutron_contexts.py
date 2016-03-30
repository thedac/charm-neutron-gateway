# vim: set ts=4:et
import os
import uuid
import socket
from charmhelpers.core.hookenv import (
    config,
    unit_get,
    cached
)
from charmhelpers.fetch import (
    apt_install,
)
from charmhelpers.contrib.openstack.context import (
    OSContextGenerator,
    NeutronAPIContext,
    config_flags_parser,
    AppArmorContext,
)
from charmhelpers.contrib.hahelpers.cluster import(
    eligible_leader
)
from charmhelpers.contrib.network.ip import (
    get_address_in_network,
)

NEUTRON_ML2_PLUGIN = "ml2"
NEUTRON_N1KV_PLUGIN = \
    "neutron.plugins.cisco.n1kv.n1kv_neutron_plugin.N1kvNeutronPluginV2"
NEUTRON_NSX_PLUGIN = "vmware"
NEUTRON_OVS_ODL_PLUGIN = "ml2"

OVS = 'ovs'
N1KV = 'n1kv'
NSX = 'nsx'
OVS_ODL = 'ovs-odl'

NEUTRON = 'neutron'

CORE_PLUGIN = {
    OVS: NEUTRON_ML2_PLUGIN,
    N1KV: NEUTRON_N1KV_PLUGIN,
    NSX: NEUTRON_NSX_PLUGIN,
    OVS_ODL: NEUTRON_OVS_ODL_PLUGIN,
}

NEUTRON_DHCP_AA_PROFILE = 'usr.bin.neutron-dhcp-agent'
NEUTRON_L3_AA_PROFILE = 'usr.bin.neutron-l3-agent'
NEUTRON_LBAAS_AA_PROFILE = 'usr.bin.neutron-lbaas-agent'
NEUTRON_METADATA_AA_PROFILE = 'usr.bin.neutron-metadata-agent'
NEUTRON_METERING_AA_PROFILE = 'usr.bin.neutron-metering-agent'
NOVA_API_METADATA_AA_PROFILE = 'usr.bin.nova-api-metadata'


def core_plugin():
    return CORE_PLUGIN[config('plugin')]


class L3AgentContext(OSContextGenerator):

    def __call__(self):
        api_settings = NeutronAPIContext()()
        ctxt = {}
        if config('run-internal-router') == 'leader':
            ctxt['handle_internal_only_router'] = eligible_leader(None)

        if config('run-internal-router') == 'all':
            ctxt['handle_internal_only_router'] = True

        if config('run-internal-router') == 'none':
            ctxt['handle_internal_only_router'] = False

        if config('external-network-id'):
            ctxt['ext_net_id'] = config('external-network-id')
        if config('plugin'):
            ctxt['plugin'] = config('plugin')
        if api_settings['enable_dvr']:
            ctxt['agent_mode'] = 'dvr_snat'
        else:
            ctxt['agent_mode'] = 'legacy'
        return ctxt


class NeutronGatewayContext(NeutronAPIContext):

    def __call__(self):
        api_settings = super(NeutronGatewayContext, self).__call__()
        ctxt = {
            'shared_secret': get_shared_secret(),
            'local_ip':
            get_address_in_network(config('os-data-network'),
                                   get_host_ip(unit_get('private-address'))),
            'core_plugin': core_plugin(),
            'plugin': config('plugin'),
            'debug': config('debug'),
            'verbose': config('verbose'),
            'instance_mtu': config('instance-mtu'),
            'l2_population': api_settings['l2_population'],
            'enable_dvr': api_settings['enable_dvr'],
            'enable_l3ha': api_settings['enable_l3ha'],
            'overlay_network_type':
            api_settings['overlay_network_type'],
        }

        mappings = config('bridge-mappings')
        if mappings:
            ctxt['bridge_mappings'] = ','.join(mappings.split())

        flat_providers = config('flat-network-providers')
        if flat_providers:
            ctxt['network_providers'] = ','.join(flat_providers.split())

        vlan_ranges = config('vlan-ranges')
        if vlan_ranges:
            ctxt['vlan_ranges'] = ','.join(vlan_ranges.split())

        dnsmasq_flags = config('dnsmasq-flags')
        if dnsmasq_flags:
            ctxt['dnsmasq_flags'] = config_flags_parser(dnsmasq_flags)

        net_dev_mtu = api_settings['network_device_mtu']
        if net_dev_mtu:
            ctxt['network_device_mtu'] = net_dev_mtu
            ctxt['veth_mtu'] = net_dev_mtu

        return ctxt


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


SHARED_SECRET = "/etc/{}/secret.txt"


def get_shared_secret():
    secret = None
    _path = SHARED_SECRET.format(NEUTRON)
    if not os.path.exists(_path):
        secret = str(uuid.uuid4())
        with open(_path, 'w') as secret_file:
            secret_file.write(secret)
    else:
        with open(_path, 'r') as secret_file:
            secret = secret_file.read().strip()
    return secret


class NeutronDHCPAppArmorContext(AppArmorContext):

    def __init__(self):
        super(NeutronDHCPAppArmorContext, self).__init__()
        self.aa_profile = NEUTRON_DHCP_AA_PROFILE

    def __call__(self):
        super(NeutronDHCPAppArmorContext, self).__call__()
        if not self.ctxt:
            return self.ctxt
        self._ctxt.update({'aa-profile': self.aa_profile})
        return self.ctxt


class NeutronL3AppArmorContext(AppArmorContext):

    def __init__(self):
        super(NeutronL3AppArmorContext, self).__init__()
        self.aa_profile = NEUTRON_L3_AA_PROFILE

    def __call__(self):
        super(NeutronL3AppArmorContext, self).__call__()
        if not self.ctxt:
            return self.ctxt
        self._ctxt.update({'aa-profile': self.aa_profile})
        return self.ctxt


class NeutronLBAASAppArmorContext(AppArmorContext):

    def __init__(self):
        super(NeutronLBAASAppArmorContext, self).__init__()
        self.aa_profile = NEUTRON_LBAAS_AA_PROFILE

    def __call__(self):
        super(NeutronLBAASAppArmorContext, self).__call__()
        if not self.ctxt:
            return self.ctxt
        self._ctxt.update({'aa-profile': self.aa_profile})
        return self.ctxt


class NeutronMetadataAppArmorContext(AppArmorContext):

    def __init__(self):
        super(NeutronMetadataAppArmorContext, self).__init__()
        self.aa_profile = NEUTRON_METADATA_AA_PROFILE

    def __call__(self):
        super(NeutronMetadataAppArmorContext, self).__call__()
        if not self.ctxt:
            return self.ctxt
        self._ctxt.update({'aa-profile': self.aa_profile})
        return self.ctxt


class NeutronMeteringAppArmorContext(AppArmorContext):

    def __init__(self):
        super(NeutronMeteringAppArmorContext, self).__init__()
        self.aa_profile = NEUTRON_METERING_AA_PROFILE

    def __call__(self):
        super(NeutronMeteringAppArmorContext, self).__call__()
        if not self.ctxt:
            return self.ctxt
        self._ctxt.update({'aa-profile': self.aa_profile})
        return self.ctxt


class NovaAPIMetadataAppArmorContext(AppArmorContext):

    def __init__(self):
        super(NovaAPIMetadataAppArmorContext, self).__init__()
        self.aa_profile = NOVA_API_METADATA_AA_PROFILE

    def __call__(self):
        super(NovaAPIMetadataAppArmorContext, self).__call__()
        if not self.ctxt:
            return self.ctxt
        self._ctxt.update({'aa-profile': self.aa_profile})
        return self.ctxt
