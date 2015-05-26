# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_log import log as logging
import oslo_messaging

from senlin.common import consts
from senlin.common.i18n import _LI
from senlin.common import messaging as rpc_messaging
from senlin.openstack.common import service

LOG = logging.getLogger(__name__)

OPERATIONS = (
    START_ACTION, CANCEL_ACTION, STOP
) = (
    'start_action', 'cancel_action', 'stop'
)


class Dispatcher(service.Service):
    '''Listen on an AMQP queue named for the engine.

    Receive notification from engine services and schedule actions.
    '''
    def __init__(self, engine_service, topic, version, thread_group_mgr):
        super(Dispatcher, self).__init__()
        self.TG = thread_group_mgr
        self.engine_id = engine_service.engine_id
        self.topic = topic
        self.version = version

    def start(self):
        super(Dispatcher, self).start()
        self.target = oslo_messaging.Target(server=self.engine_id,
                                            topic=self.topic,
                                            version=self.version)
        server = rpc_messaging.get_rpc_server(self.target, self)
        server.start()

    def listening(self, context):
        '''Respond affirmatively to confirm that engine is still alive.'''
        return True

    def start_action(self, context, action_id=None):
        self.TG.start_action(context, action_id, self.engine_id)

    def cancel_action(self, context, action_id):
        '''Cancel an action.'''
        self.TG.cancel_action(context, action_id)

    def suspend_action(self, context, action_id):
        '''Suspend an action.'''
        self.TG.suspend_action(context, action_id)

    def resume_action(self, context, action_id):
        '''Resume an action.'''
        self.TG.resume_action(context, action_id)

    def stop(self):
        super(Dispatcher, self).stop()
        # Wait for all action threads to be finished
        LOG.info(_LI("Stopping all action threads of engine %s"),
                 self.engine_id)
        # Stop ThreadGroup gracefully
        self.TG.stop(True)
        LOG.info(_LI("All action threads have been finished"))


def notify(context, method, engine_id=None, **kwargs):
    '''Send notification to dispatcher

    :param context: rpc request context
    :param method: remote method to call
    :param engine_id: dispatcher to notify; None implies broadcast
    '''

    client = rpc_messaging.get_rpc_client(version=consts.RPC_API_VERSION)

    if engine_id:
        # Notify specific dispatcher identified by engine_id
        call_context = client.prepare(
            version=consts.RPC_API_VERSION,
            topic=consts.ENGINE_DISPATCHER_TOPIC,
            server=engine_id)
    else:
        # Broadcast to all disptachers
        call_context = client.prepare(
            version=consts.RPC_API_VERSION,
            topic=consts.ENGINE_DISPATCHER_TOPIC)

    try:
        call_context.call(context, method, **kwargs)
        return True
    except oslo_messaging.MessagingTimeout:
        return False


def start_action(context, engine_id=None, **kwargs):
    return notify(context, START_ACTION, engine_id, **kwargs)
