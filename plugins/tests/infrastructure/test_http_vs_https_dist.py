'''
test_http_vs_https_dist.py

Copyright 2011 Andres Riancho

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
'''
import copy
import unittest

from mock import MagicMock, Mock, create_autospec
from mock import patch, call

import plugins.infrastructure.http_vs_https_dist as hvshsdist
import core.controllers.output_manager as om
import core.data.kb.knowledge_base as kb

from plugins.tests.helper import PluginTest, PluginConfig
from core.data.parsers.url import URL
from core.data.request.fuzzable_request import FuzzableRequest
from core.controllers.exceptions import w3afRunOnce
from plugins.tests.helper import onlyroot


class test_http_vs_https_dist(unittest.TestCase):
    '''
    :author: Javier Andalia <jandalia =at= gmail.com>
    '''

    test_url = URL('http://host.tld')
    tracedict = {'localhost': {1: ('192.168.1.1', False),
                               3: ('200.115.195.33', False),
                               5: ('207.46.47.14', True)}}

    def setUp(self):
        kb.kb.cleanup()

    def test_discover_override_port(self):
        plugininst = hvshsdist.http_vs_https_dist()
        # pylint: disable=E0202
        # An attribute affected in plugins.tests.infrastructure.
        # test_http_vs_https_dist line 53 hide this method
        plugininst._has_permission = MagicMock(return_value=True)

        url = URL('https://host.tld:4444/')
        fuzz_req = FuzzableRequest(url)

        # HTTPS and HTTP responses, with one different hop
        tracedict1 = copy.deepcopy(self.tracedict)
        tracedict2 = copy.deepcopy(self.tracedict)
        tracedict2['localhost'][3] = ('200.200.0.0', False)
        self._mock_traceroute(tracedict1, tracedict2)

        # Mock output manager. Ensure that is called with the proper desc.
        om.out.information = MagicMock(return_value=True)
        plugininst.discover(fuzz_req)

        result = ('Routes to target "host.tld" using ports 80 and 4444 are different:\n'\
                  '  TCP trace to host.tld:80\n    0 192.168.1.1\n    1 200.200.0.0\n    2 207.46.47.14\n'\
                  '  TCP trace to host.tld:4444\n    0 192.168.1.1\n    1 200.115.195.33\n    2 207.46.47.14')
        om.out.information.assert_called_once_with(result)

    def test_discover_eq_routes(self):
        plugininst = hvshsdist.http_vs_https_dist()
        plugininst._has_permission = MagicMock(return_value=True)

        url = URL('https://host.tld:80/')
        fuzz_req = FuzzableRequest(url)

        # HTTPS and HTTP responses, with the same hops
        tracedict1 = copy.deepcopy(self.tracedict)
        tracedict2 = copy.deepcopy(self.tracedict)
        self._mock_traceroute(tracedict1, tracedict2)

        # Mock output manager. Ensure that is called with the proper desc.
        om.out.information = MagicMock(
            side_effect=ValueError('Unexpected call.'))
        plugininst.discover(fuzz_req)

        infos = kb.kb.get('http_vs_https_dist', 'http_vs_https_dist')
        self.assertEqual(len(infos), 1)

        info = infos[0]
        self.assertEqual('HTTP traceroute', info.get_name())
        self.assertTrue('are the same' in info.get_desc())

    def test_discover_diff_routes(self):
        plugininst = hvshsdist.http_vs_https_dist()
        plugininst._has_permission = MagicMock(return_value=True)

        url = URL('https://host.tld/')
        fuzz_req = FuzzableRequest(url)

        # HTTPS and HTTP responses, with one different hop
        tracedict1 = copy.deepcopy(self.tracedict)
        tracedict2 = copy.deepcopy(self.tracedict)
        tracedict2['localhost'][3] = ('200.200.0.0', False)
        self._mock_traceroute(tracedict1, tracedict2)

        # Mock output manager. Ensure that is called with the proper desc.
        om.out.information = MagicMock(return_value=True)
        plugininst.discover(fuzz_req)

        result = ('Routes to target "host.tld" using ports 80 and 443 are different:\n'\
                  '  TCP trace to host.tld:80\n    0 192.168.1.1\n    1 200.200.0.0\n    2 207.46.47.14\n'\
                  '  TCP trace to host.tld:443\n    0 192.168.1.1\n    1 200.115.195.33\n    2 207.46.47.14')
        om.out.information.assert_called_once_with(result)

    def test_discover_runonce(self):
        ''' Discovery routine must be executed only once. Upcoming calls should
        fail'''
        url = URL('https://host.tld/')
        fuzz_req = FuzzableRequest(url)

        plugininst = hvshsdist.http_vs_https_dist()
        plugininst._has_permission = MagicMock(side_effect=[True, True])

        plugininst.discover(fuzz_req)
        self.assertRaises(w3afRunOnce, plugininst.discover, fuzz_req)

    def test_not_root_user(self):
        plugininst = hvshsdist.http_vs_https_dist()

        plugininst._has_permission = MagicMock(return_value=False)

        with patch('plugins.infrastructure.http_vs_https_dist.om.out') as om_mock:
            plugininst.discover(None)
            ecall = call.error(hvshsdist.PERM_ERROR_MSG)
            self.assertIn(ecall, om_mock.mock_calls)

    def _mock_traceroute(self, trace_resp_1, trace_resp_2):
        '''
        Helper method: Mocks scapy 'traceroute' function
        '''
        https_tracerout_obj_1 = Mock()
        https_tracerout_obj_1.get_trace = MagicMock(return_value=trace_resp_1)
        resp_tuple_1 = (https_tracerout_obj_1, None)

        https_tracerout_obj_2 = Mock()
        https_tracerout_obj_2.get_trace = MagicMock(return_value=trace_resp_2)
        resp_tuple_2 = (https_tracerout_obj_2, None)

        hvshsdist.traceroute = create_autospec(hvshsdist.traceroute,
                                               side_effect=[resp_tuple_1, resp_tuple_2])


class TestHTTPvsHTTPS(PluginTest):

    base_url = 'http://moth/'

    _run_configs = {
        'cfg': {
        'target': base_url,
        'plugins': {'infrastructure': (PluginConfig('http_vs_https_dist'),)}
        }
    }

    @onlyroot
    def test_trace(self):
        cfg = self._run_configs['cfg']
        self._scan(cfg['target'], cfg['plugins'])

        infos = self.kb.get('http_vs_https_dist', 'http_vs_https_dist')

        self.assertEqual(len(infos), 1, infos)

        info = infos[0]
        self.assertEqual('HTTP traceroute', info.get_name())
