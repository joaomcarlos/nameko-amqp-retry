import sys

from nameko.messaging import Consumer as NamekoConsumer

from nameko_amqp_retry import Backoff, BackoffPublisher
from nameko_amqp_retry.constants import CALL_ID_STACK_HEADER_KEY


class Consumer(NamekoConsumer):

    backoff_publisher = BackoffPublisher()

    def handle_result(self, message, worker_ctx, result=None, exc_info=None):

        if exc_info is not None:
            exc_type = exc_info[0]
            if issubclass(exc_type, Backoff):

                # add call stack and modify the current entry to show backoff
                message.headers[CALL_ID_STACK_HEADER_KEY] = (
                    worker_ctx.call_id_stack
                )
                message.headers[CALL_ID_STACK_HEADER_KEY][-1] += ".backoff"

                redeliver_to = self.queue.name
                try:
                    self.backoff_publisher.republish(
                        exc_type, message, redeliver_to
                    )
                except Backoff.Expired:
                    exc_info = sys.exc_info()
                    result = None

        self.handle_message_processed(message, result, exc_info)
        return result, exc_info


consume = Consumer.decorator
