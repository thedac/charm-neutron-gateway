#!/usr/bin/python

from quantumclient.v2_0 import client
from keystoneclient.v2_0 import client as ks_client
import optparse
import os
import sys
import logging

usage = "Usage: %prog [options] name cidr"

if __name__ == '__main__':
    parser = optparse.OptionParser(usage)
    parser.add_option('-t', '--tenant',
                      help='Tenant name to create private network for',
                      dest='tenant', action='store',
                      default=os.environ['OS_TENANT_NAME'])
    parser.add_option('-s', '--shared',
                      help='Create a shared rather than private network',
                      dest='shared', action='store_true', default=False)
    parser.add_option('-r', '--router',
                      help='Router to plug new network into',
                      dest='router', action='store', default=None)
    parser.add_option("-d", "--debug",
                      help="Enable debug logging",
                      dest="debug", action="store_true",  default=False)
    (opts, args) = parser.parse_args()

    if len(args) != 2:
        parser.print_help()
        sys.exit(1)

    if opts.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    net_name = args[0]
    subnet_name = "{}_subnet".format(net_name)
    cidr = args[1]

    keystone = ks_client.Client(username=os.environ['OS_USERNAME'],
                                password=os.environ['OS_PASSWORD'],
                                tenant_name=os.environ['OS_TENANT_NAME'],
                                auth_url=os.environ['OS_AUTH_URL'])
    quantum = client.Client(username=os.environ['OS_USERNAME'],
                            password=os.environ['OS_PASSWORD'],
                            tenant_name=os.environ['OS_TENANT_NAME'],
                            auth_url=os.environ['OS_AUTH_URL'])

    # Resolve tenant id
    tenant_id = None
    for tenant in [t._info for t in keystone.tenants.list()]:
        if tenant['name'] == opts.tenant:
            tenant_id = tenant['id']
            break  # Tenant ID found - stop looking
    if not tenant_id:
        logging.error("Unable to locate tenant id for %s.", opts.tenant)
        sys.exit(1)

    # Create network
    networks = quantum.list_networks(name=net_name)
    if len(networks['networks']) == 0:
        logging.info('Creating network: %s',
                     net_name)
        network_msg = {
            'network': {
                'name': net_name,
                'shared': opts.shared,
                'tenant_id': tenant_id
            }
        }
        network = quantum.create_network(network_msg)
    else:
        logging.error('Network %s already exists.', net_name)
        network = networks['networks'][0]

    # Create subnet
    subnets = quantum.list_subnets(name=subnet_name)
    if len(subnets['subnets']) == 0:
        logging.info('Creating subnet for %s',
                     net_name)
        subnet_msg = {
            'subnet': {
                'name': subnet_name,
                'network_id': network['id'],
                'enable_dhcp': True,
                'cidr': cidr,
                'ip_version': 4,
                'tenant_id': tenant_id
            }
        }
        subnet = quantum.create_subnet(subnet_msg)
    else:
        logging.warning('Subnet %s already exists.', subnet_name)
        subnet = subnets['subnets'][0]

    # Plug subnet into router
    if opts.router:
        routers = quantum.list_routers(name=opts.router)
        if len(routers['routers']) == 0:
            logging.error('Unable to locate router %s', opts.router)
            sys.exit(1)
        else:
            logging.info('Adding interface from %s to %s',
                         opts.router, subnet_name)
            router = routers['routers'][0]
            quantum.add_interface_router(router['id'],
                                         {'subnet_id': subnet['id']})
