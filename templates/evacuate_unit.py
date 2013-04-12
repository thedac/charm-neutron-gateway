#!/usr/bin/python

import subprocess


def log(priority, message):
    print "{}: {}".format(priority, message)

DHCP_AGENT = "DHCP Agent"
L3_AGENT = "L3 Agent"


def evacuate_unit(unit):
    ''' Use agent scheduler API to detect down agents and re-schedule '''
    from quantumclient.v2_0 import client
    # TODO: Fixup for https keystone
    auth_url = 'http://{{ keystone_host }}:{{ auth_port }}/v2.0'
    quantum = client.Client(username='{{ service_username }}',
                            password='{{ service_password }}',
                            tenant_name='{{ service_tenant }}',
                            auth_url=auth_url,
                            region_name='{{ region }}')

    agents = quantum.list_agents(agent_type=DHCP_AGENT)
    dhcp_agents = []
    l3_agents = []
    networks = {}
    for agent in agents['agents']:
        if agent['alive'] and agent['host'] != unit:
            dhcp_agents.append(agent['id'])
        elif agent['host'] == unit:
            log('INFO', 'DHCP Agent %s down' % agent['id'])
            for network in \
                quantum.list_networks_on_dhcp_agent(agent['id'])['networks']:
                networks[network['id']] = agent['id']

    agents = quantum.list_agents(agent_type=L3_AGENT)
    routers = {}
    for agent in agents['agents']:
        if agent['alive'] and agent['host'] != unit:
            l3_agents.append(agent['id'])
        elif agent['host'] == unit:
            for router in \
                quantum.list_routers_on_l3_agent(agent['id'])['routers']:
                routers[router['id']] = agent['id']

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

evacuate_unit(subprocess.check_call(['hostname', '-f']))
