# vim: set ts=4:et
from charmhelpers.core.hookenv import (
    config,
    relation_ids,
    related_units,
    relation_get,
)
from charmhelpers.contrib.openstack.context import (
    OSContextGenerator,
    context_complete
)
import quantum_utils as qutils


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
            'shared_secret': qutils.get_shared_secret(),
            'local_ip': qutils.get_host_ip(),
            'core_plugin': qutils.CORE_PLUGIN[config('plugin')],
            'plugin': config('plugin')
        }
        return ctxt
