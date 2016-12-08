import pytest
from mock import Mock, call, patch

from nameko_amqp_retry import Backoff

BACKOFF_COUNT = 3


class TestGetNextExpiration(object):

    @pytest.fixture
    def backoff(self):
        class CustomBackoff(Backoff):
            schedule = [1000, 2000, 3000]
            randomness = 0
            limit = 10

        return CustomBackoff()

    @pytest.fixture
    def backoff_without_limit(self):
        class CustomBackoff(Backoff):
            schedule = [1000, 2000, 3000]
            randomness = 0
            limit = 0  # no limit

        return CustomBackoff()

    @pytest.fixture
    def backoff_with_randomness(self):
        class CustomBackoff(Backoff):
            schedule = [1000, 2000, 3000]
            randomness = 100
            limit = 10

        return CustomBackoff()

    def test_first_backoff(self, backoff):
        message = Mock()
        message.headers = {}
        assert backoff.get_next_expiration(message, "backoff") == 1000

    def test_next_backoff(self, backoff):
        message = Mock()
        message.headers = {
            'x-death': [{
                'exchange': 'backoff',
                'count': 1
            }]
        }
        assert backoff.get_next_expiration(message, "backoff") == 2000

    def test_last_backoff(self, backoff):
        message = Mock()
        message.headers = {
            'x-death': [{
                'exchange': 'backoff',
                'count': 3
            }]
        }
        assert backoff.get_next_expiration(message, "backoff") == 3000

    def test_count_greater_than_schedule_length(self, backoff):
        message = Mock()
        message.headers = {
            'x-death': [{
                'exchange': 'backoff',
                'count': 5
            }]
        }
        assert backoff.get_next_expiration(message, "backoff") == 3000

    def test_count_greater_than_limit(self, backoff):
        message = Mock()
        message.headers = {
            'x-death': [{
                'exchange': 'backoff',
                'count': 99
            }]
        }
        with pytest.raises(Backoff.Expired) as exc_info:
            backoff.get_next_expiration(message, "backoff")
        # 27 = 1 + 2 + 3 * 8
        assert str(exc_info.value) == (
            "Backoff aborted after '10' retries (~27 seconds)"
        )

    def test_count_equal_to_limit(self, backoff):
        message = Mock()
        message.headers = {
            'x-death': [{
                'exchange': 'backoff',
                'count': 10
            }]
        }
        with pytest.raises(Backoff.Expired) as exc_info:
            backoff.get_next_expiration(message, "backoff")
        # 27 = 1 + 2 + 3 * 8
        assert str(exc_info.value) == (
            "Backoff aborted after '10' retries (~27 seconds)"
        )

    def test_previously_deadlettered_first_backoff(self, backoff):
        message = Mock()
        message.headers = {
            'x-death': [{
                # previously deadlettered elsewhere
                'exchange': 'not-backoff',
                'count': 99
            }]
        }
        assert backoff.get_next_expiration(message, "backoff") == 1000

    def test_previously_deadlettered_next_backoff(self, backoff):
        message = Mock()
        message.headers = {
            'x-death': [{
                'exchange': 'backoff',
                'count': 1
            }, {
                # previously deadlettered elsewhere
                'exchange': 'not-backoff',
                'count': 99
            }]
        }
        assert backoff.get_next_expiration(message, "backoff") == 2000

    def test_no_limit(self, backoff_without_limit):

        backoff = backoff_without_limit

        message = Mock()
        message.headers = {
            'x-death': [{
                'exchange': 'backoff',
                'count': 999
            }]
        }
        assert backoff.get_next_expiration(message, "backoff") == 3000

    @patch('nameko_amqp_retry.backoff.random')
    def test_backoff_randomness(self, random_patch, backoff_with_randomness):

        random_patch.gauss.return_value = 2200.0

        backoff = backoff_with_randomness

        message = Mock()
        message.headers = {
            'x-death': [{
                'exchange': 'backoff',
                'count': 1
            }]
        }
        assert backoff.get_next_expiration(message, "backoff") == 2200
        assert random_patch.gauss.call_args_list == [
            call(2000, backoff.randomness)
        ]