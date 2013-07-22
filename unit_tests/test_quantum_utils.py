from mock import MagicMock, patch, call
import charmhelpers.contrib.openstack.templating as templating
templating.OSConfigRenderer = MagicMock()
import quantum_utils
from collections import OrderedDict

from test_utils import (
    CharmTestCase
)

TO_PATCH = [
    'get_os_codename_package',
    'config',
    'get_os_codename_install_source',
    'apt_update',
    'apt_install',
    'configure_installation_source',
    'log',
    'add_bridge',
    'add_bridge_port'
]


class TestQuantumUtils(CharmTestCase):
    def setUp(self):
        super(TestQuantumUtils, self).setUp(quantum_utils, TO_PATCH)

    def test_valid_plugin(self):
        self.config.return_value = 'ovs'
        self.assertTrue(quantum_utils.valid_plugin())
        self.config.return_value = 'nvp'
        self.assertTrue(quantum_utils.valid_plugin())

    def test_invalid_plugin(self):
        self.config.return_value = 'invalid'
        self.assertFalse(quantum_utils.valid_plugin())

    def test_get_early_packages_ovs(self):
        self.config.return_value = 'ovs'
        self.assertEquals(quantum_utils.get_early_packages(),
                          ['openvswitch-datapath-dkms'])

    def test_get_early_packages_nvp(self):
        self.config.return_value = 'nvp'
        self.assertEquals(quantum_utils.get_early_packages(),
                          [])

    def test_get_packages_ovs(self):
        self.config.return_value = 'ovs'
        self.assertNotEqual(quantum_utils.get_packages(), [])

    def test_configure_ovs_ovs_ext_port(self):
        self.config.side_effect = self.test_config.get
        self.test_config.set('plugin', 'ovs')
        self.test_config.set('ext-port', 'eth0')
        quantum_utils.configure_ovs()
        self.add_bridge.assert_has_calls([
            call('br-int'),
            call('br-ex')
        ])
        self.add_bridge_port.assert_called_with('br-ex', 'eth0')

    def test_configure_ovs_nvp(self):
        self.config.return_value = 'nvp'
        quantum_utils.configure_ovs()
        self.add_bridge.assert_called_with('br-int')

    def test_do_openstack_upgrade(self):
        self.config.side_effect = self.test_config.get
        self.test_config.set('openstack-origin', 'cloud:precise-havana')
        self.test_config.set('plugin', 'ovs')
        self.config.return_value = 'cloud:precise-havana'
        self.get_os_codename_install_source.return_value = 'havana'
        configs = MagicMock()
        quantum_utils.do_openstack_upgrade(configs)
        configs.set_release.assert_called_with(openstack_release='havana')
        self.log.assert_called()
        self.apt_update.assert_called_with(fatal=True)
        dpkg_opts = [
            '--option', 'Dpkg::Options::=--force-confnew',
            '--option', 'Dpkg::Options::=--force-confdef',
        ]
        self.apt_install.assert_called_with(
            packages=quantum_utils.GATEWAY_PKGS['ovs'],
            options=dpkg_opts, fatal=True
        )
        self.configure_installation_source.assert_called_with(
            'cloud:precise-havana'
        )

    def test_register_configs_ovs(self):
        self.config.return_value = 'ovs'
        self.get_os_codename_package.return_value = 'havana'
        configs = quantum_utils.register_configs()
        confs = [quantum_utils.DHCP_AGENT_CONF,
                 quantum_utils.METADATA_AGENT_CONF,
                 quantum_utils.NOVA_CONF,
                 quantum_utils.QUANTUM_CONF,
                 quantum_utils.L3_AGENT_CONF,
                 quantum_utils.OVS_PLUGIN_CONF,
                 quantum_utils.EXT_PORT_CONF]
        for conf in confs:
            configs.register.assert_any_call(
                conf,
                quantum_utils.CONFIG_FILES[quantum_utils.OVS][conf]
                                          ['hook_contexts']
            )

    def test_restart_map_ovs(self):
        self.config.return_value = 'ovs'
        ex_map = OrderedDict([
            (quantum_utils.L3_AGENT_CONF, ['quantum-l3-agent']),
            (quantum_utils.OVS_PLUGIN_CONF,
             ['quantum-plugin-openvswitch-agent']),
            (quantum_utils.NOVA_CONF, ['nova-api-metadata']),
            (quantum_utils.METADATA_AGENT_CONF, ['quantum-metadata-agent']),
            (quantum_utils.DHCP_AGENT_CONF, ['quantum-dhcp-agent']),
            (quantum_utils.QUANTUM_CONF, ['quantum-l3-agent',
                                          'quantum-dhcp-agent',
                                          'quantum-metadata-agent',
                                          'quantum-plugin-openvswitch-agent'])
        ])
        self.assertEquals(quantum_utils.restart_map(), ex_map)

    def test_register_configs_nvp(self):
        self.config.return_value = 'nvp'
        self.get_os_codename_package.return_value = 'havana'
        configs = quantum_utils.register_configs()
        confs = [quantum_utils.DHCP_AGENT_CONF,
                 quantum_utils.METADATA_AGENT_CONF,
                 quantum_utils.NOVA_CONF,
                 quantum_utils.QUANTUM_CONF]
        for conf in confs:
            configs.register.assert_any_call(
                conf,
                quantum_utils.CONFIG_FILES[quantum_utils.NVP][conf]
                                          ['hook_contexts']
            )

    def test_restart_map_nvp(self):
        self.config.return_value = 'nvp'
        ex_map = OrderedDict([
            (quantum_utils.DHCP_AGENT_CONF, ['quantum-dhcp-agent']),
            (quantum_utils.NOVA_CONF, ['nova-api-metadata']),
            (quantum_utils.QUANTUM_CONF, ['quantum-dhcp-agent',
                                          'quantum-metadata-agent']),
            (quantum_utils.METADATA_AGENT_CONF, ['quantum-metadata-agent']),
        ])
        self.assertEquals(quantum_utils.restart_map(), ex_map)

    def test_register_configs_pre_install(self):
        self.config.return_value = 'ovs'
        self.get_os_codename_package.return_value = None
        configs = quantum_utils.register_configs()
        confs = [quantum_utils.DHCP_AGENT_CONF,
                 quantum_utils.METADATA_AGENT_CONF,
                 quantum_utils.NOVA_CONF,
                 quantum_utils.QUANTUM_CONF,
                 quantum_utils.L3_AGENT_CONF,
                 quantum_utils.OVS_PLUGIN_CONF,
                 quantum_utils.EXT_PORT_CONF]
        for conf in confs:
            configs.register.assert_any_call(
                conf,
                quantum_utils.CONFIG_FILES[quantum_utils.OVS][conf]
                                          ['hook_contexts']
            )


