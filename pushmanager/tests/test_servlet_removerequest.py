import types
from contextlib import nested

import mock
import testify as T
from pushmanager.core import db
from pushmanager.core.util import get_servlet_urlspec
from pushmanager.servlets.removerequest import RemoveRequestServlet
from pushmanager.testing.mocksettings import MockedSettings
from pushmanager.testing.testservlet import ServletTestMixin


class RemoveRequestServletTest(T.TestCase, ServletTestMixin):

    def get_handlers(self):
        return [get_servlet_urlspec(RemoveRequestServlet)]

    def test_removerequest(self):
        results = []

        def on_db_return(success, db_results):
            assert success
            results.extend(db_results.fetchall())

        with nested(
            mock.patch.dict(db.Settings, MockedSettings),
            mock.patch.object(
                RemoveRequestServlet,
                "get_current_user",
                return_value="testuser"
            )
        ):
            results = []
            db.execute_cb(db.push_pushcontents.select(), on_db_return)
            num_results_before = len(results)

            uri = "/removerequest?request=1&push=1"
            response = self.fetch(uri)
            T.assert_equal(response.error, None)

            results = []
            db.execute_cb(db.push_pushcontents.select(), on_db_return)
            num_results_after = len(results)

            T.assert_equal(num_results_after, num_results_before - 1, "Request removal failed.")

    def call_on_db_complete(self):
        mocked_self = mock.Mock()
        mocked_self.current_user = 'fake_pushmaster'
        mocked_self.pushid = 0
        mocked_self.check_db_results = mock.Mock(return_value=None)

        mocked_self.on_db_complete = types.MethodType(RemoveRequestServlet.on_db_complete.im_func, mocked_self)

        no_watcher_req = {
            'id': 0,
            'user': 'testuser',
            'watchers': None,
            'repo': 'repo',
            'branch': 'branch',
            'title': 'title',
            'state': 'added',
        }
        watched_req = {
            'id': 0,
            'user': 'testuser',
            'watchers': 'testuser1,testuser2',
            'repo': 'repo',
            'branch': 'branch',
            'title': 'title',
            'state': 'added',
        }
        reqs = [no_watcher_req, watched_req]

        mocked_self.on_db_complete('success', [reqs, mock.ANY, mock.ANY])

    @mock.patch('pushmanager.core.db.execute_transaction_cb')
    @mock.patch('pushmanager.core.xmppclient.XMPPQueue.enqueue_user_xmpp')
    @mock.patch('pushmanager.core.mail.MailQueue.enqueue_user_email')
    def test_mailqueue_on_db_complete(self, mailq, *_):
        self.call_on_db_complete()

        no_watcher_call_args = mailq.call_args_list[0][0]
        T.assert_equal(['testuser'], no_watcher_call_args[0])
        T.assert_in('for testuser', no_watcher_call_args[1])
        T.assert_in('testuser - title', no_watcher_call_args[1])
        T.assert_in('[push] testuser - title', no_watcher_call_args[2])

        watched_call_args = mailq.call_args_list[1][0]
        T.assert_equal(['testuser', 'testuser1', 'testuser2'], watched_call_args[0])
        T.assert_in('for testuser (testuser1,testuser2)', watched_call_args[1])
        T.assert_in('testuser (testuser1,testuser2) - title', watched_call_args[1])
        T.assert_in('[push] testuser (testuser1,testuser2) - title', watched_call_args[2])

    @mock.patch('pushmanager.core.db.execute_transaction_cb')
    @mock.patch('pushmanager.core.mail.MailQueue.enqueue_user_email')
    @mock.patch('pushmanager.core.xmppclient.XMPPQueue.enqueue_user_xmpp')
    def test_xmppqueue_on_db_complete(self, xmppq, *_):
        self.call_on_db_complete()

        no_watcher_call_args = xmppq.call_args_list[0][0]
        T.assert_equal(['testuser'], no_watcher_call_args[0])
        T.assert_in('for testuser', no_watcher_call_args[1])

        watched_call_args = xmppq.call_args_list[1][0]
        T.assert_equal(['testuser', 'testuser1', 'testuser2'], watched_call_args[0])
        T.assert_in('for testuser (testuser1,testuser2)', watched_call_args[1])


if __name__ == '__main__':
    T.run()
