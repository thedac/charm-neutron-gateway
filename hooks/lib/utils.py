#
# Copyright 2012 Canonical Ltd.
#
# This file is sourced from lp:openstack-charm-helpers
#
# Authors:
#  James Page <james.page@ubuntu.com>
#  Paul Collins <paul.collins@canonical.com>
#  Adam Gandelman <adamg@ubuntu.com>
#

import socket
from charmhelpers.core.host import (
    apt_install
)
from charmhelpers.core.hookenv import (
    unit_get,
    cached
)


TEMPLATES_DIR = 'templates'

try:
    import jinja2
except ImportError:
    apt_install('python-jinja2', fatal=True)
    import jinja2

try:
    import dns.resolver
except ImportError:
    apt_install('python-dnspython', fatal=True)
    import dns.resolver


def render_template(template_name, context, template_dir=TEMPLATES_DIR):
    templates = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir)
    )
    template = templates.get_template(template_name)
    return template.render(context)


@cached
def get_unit_hostname():
    return socket.gethostname()


@cached
def get_host_ip(hostname=None):
    hostname = hostname or unit_get('private-address')
    try:
        # Test to see if already an IPv4 address
        socket.inet_aton(hostname)
        return hostname
    except socket.error:
        answers = dns.resolver.query(hostname, 'A')
        if answers:
            return answers[0].address
    return None
