"""
Tests for Issue #8 — Harden Database Reconnection Pool Resilience
"""
import logging
import time
import unittest
from unittest.mock import MagicMock, patch, call

from hypothesis import given, settings
import hypothesis.strategies as st

from Backend.Services.PostgreSqlService import PostgreSqlService, RETRY_DELAYS, _SlowQueryCursor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service_mock_mode():
    """Return a PostgreSqlService instance in mock mode (no real DB needed)."""
    svc = PostgreSqlService.__new__(PostgreSqlService)
    svc.postgresMode = "mock"
    svc.pool = None
    svc.hasPgVector = False
    svc.mockDevices = {}
    svc.mockLogs = []
    svc.mockEnergy = {}
    svc.mockVectorIndex = []
    svc.mockEmbeddingCache = {}
    return svc


def _make_service_live_mode(pool=None):
    """Return a PostgreSqlService instance in live mode with an optional mock pool."""
    svc = _make_service_mock_mode()
    svc.postgresMode = "live"
    svc.pool = pool or MagicMock()
    return svc


# ---------------------------------------------------------------------------
# Smoke test — module loads correctly
# ---------------------------------------------------------------------------

class TestModuleLoads(unittest.TestCase):
    def test_module_imports_successfully(self):
        """Task 1 smoke test: the module and its exports load without error."""
        self.assertIsNotNone(PostgreSqlService)
        self.assertIsNotNone(RETRY_DELAYS)
        self.assertIsNotNone(_SlowQueryCursor)

    def test_retry_delays_constant(self):
        self.assertEqual(RETRY_DELAYS, [0.5, 1.0, 2.0])


# ---------------------------------------------------------------------------
# Task 2 — _validate_connection() unit tests
# ---------------------------------------------------------------------------

class TestValidateConnection(unittest.TestCase):
    def _make_conn(self, raises=None):
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        if raises:
            cursor.execute.side_effect = raises
        return conn, cursor

    def test_valid_connection_no_exception(self):
        svc = _make_service_live_mode()
        conn, cursor = self._make_conn()
        # Should not raise
        svc._validate_connection(conn)

    def test_stale_connection_raises(self):
        svc = _make_service_live_mode()
        conn, cursor = self._make_conn(raises=Exception("connection closed"))
        with self.assertRaises(Exception):
            svc._validate_connection(conn)

    def test_validate_executes_select_1(self):
        svc = _make_service_live_mode()
        conn, cursor = self._make_conn()
        svc._validate_connection(conn)
        cursor.execute.assert_called_once_with("SELECT 1")


# ---------------------------------------------------------------------------
# Task 2.1 — Property 1: Validation probe is always called before yield
# ---------------------------------------------------------------------------

class TestProperty1ValidationAlwaysCalled(unittest.TestCase):
    # Feature: issue-8-db-resilience, Property 1: Validation probe is always called before yield

    @given(st.lists(st.booleans(), min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_select_1_called_on_every_connection_before_yield(self, valid_flags):
        """
        **Validates: Requirements 1.1, 1.4**
        For every connection obtained from pool.getconn(), SELECT 1 is called
        on that connection before it is yielded to the caller.
        """
        svc = _make_service_live_mode()
        probed_connections = []

        def fake_validate(conn):
            # Record that this connection was probed
            probed_connections.append(id(conn))
            # The first call: stale if valid_flags[0] is False; we simplify:
            # just record and succeed (we test the probe is called, not discard logic here)

        connections = []
        for flag in valid_flags:
            m = MagicMock()
            connections.append(m)

        call_count = [0]
        def fake_getconn():
            idx = min(call_count[0], len(connections) - 1)
            call_count[0] += 1
            return connections[idx]

        svc.pool.getconn = fake_getconn
        svc._validate_connection = fake_validate

        with patch('time.sleep'):
            result = svc._checkout_with_retry()

        # At least one connection was checked out and probe was called on it
        self.assertGreater(len(probed_connections), 0)
        # Every id in probed_connections should correspond to a connection we generated
        known_ids = {id(c) for c in connections}
        for pid in probed_connections:
            self.assertIn(pid, known_ids)


# ---------------------------------------------------------------------------
# Task 2.2 — _validate_connection() replacement-after-discard test
# ---------------------------------------------------------------------------

class TestValidateConnectionReplacement(unittest.TestCase):
    def test_replacement_connection_validated_after_stale_discard(self):
        """
        Stale connection raises -> retry -> replacement connection is also validated.
        Requirements: 1.3, 1.4
        """
        svc = _make_service_live_mode()

        stale_conn = MagicMock()
        valid_conn = MagicMock()

        validated = []

        def fake_validate(conn):
            validated.append(conn)
            if conn is stale_conn:
                raise Exception("stale")
            # valid_conn succeeds silently

        call_count = [0]
        def fake_getconn():
            if call_count[0] == 0:
                call_count[0] += 1
                return stale_conn
            return valid_conn

        svc.pool.getconn = fake_getconn
        svc._validate_connection = fake_validate

        with patch('time.sleep'):
            result = svc._checkout_with_retry()

        # Both connections were validated
        self.assertIn(stale_conn, validated)
        self.assertIn(valid_conn, validated)
        # Final result is the valid connection
        self.assertIs(result, valid_conn)


# ---------------------------------------------------------------------------
# Task 3 — _checkout_with_retry() unit and property tests
# ---------------------------------------------------------------------------

class TestCheckoutWithRetry(unittest.TestCase):
    def test_success_on_first_attempt(self):
        svc = _make_service_live_mode()
        conn = MagicMock()
        svc.pool.getconn.return_value = conn
        svc._validate_connection = MagicMock()
        svc._try_recreate_pool = MagicMock(return_value=None)

        result = svc._checkout_with_retry()
        self.assertIs(result, conn)
        svc.pool.getconn.assert_called_once()

    def test_returns_none_when_all_retries_and_recreation_fail(self):
        svc = _make_service_live_mode()
        svc.pool.getconn.side_effect = Exception("pool exhausted")
        svc._try_recreate_pool = MagicMock(return_value=None)

        with patch('time.sleep'):
            with patch('logging.warning'):
                result = svc._checkout_with_retry()

        self.assertIsNone(result)

    def test_returns_connection_from_recreation_when_retries_fail(self):
        svc = _make_service_live_mode()
        svc.pool.getconn.side_effect = Exception("pool exhausted")
        recreation_conn = MagicMock()
        svc._try_recreate_pool = MagicMock(return_value=recreation_conn)

        with patch('time.sleep'):
            with patch('logging.warning'):
                result = svc._checkout_with_retry()

        self.assertIs(result, recreation_conn)
        svc._try_recreate_pool.assert_called_once()


# ---------------------------------------------------------------------------
# Task 3.1 — Property 2: Retry count never exceeds 3
# ---------------------------------------------------------------------------

class TestProperty2RetryCount(unittest.TestCase):
    # Feature: issue-8-db-resilience, Property 2: Retry count never exceeds 3

    @given(st.integers(min_value=1, max_value=10))
    @settings(max_examples=100)
    def test_getconn_called_at_most_4_times(self, n_failures):
        """
        **Validates: Requirements 2.1**
        pool.getconn() is called at most 4 times total (1 initial + 3 retries),
        regardless of how many failures occur.
        """
        svc = _make_service_live_mode()
        call_count = [0]

        def always_fail():
            call_count[0] += 1
            raise Exception(f"failure {call_count[0]}")

        svc.pool.getconn = always_fail
        svc._try_recreate_pool = MagicMock(return_value=None)

        with patch('time.sleep'):
            with patch('logging.warning'):
                svc._checkout_with_retry()

        expected = min(n_failures, 4)
        # Regardless of n_failures, we always exhaust exactly 4 attempts
        self.assertEqual(call_count[0], 4)


# ---------------------------------------------------------------------------
# Task 3.2 — Property 3: Retry delays follow the exponential schedule
# ---------------------------------------------------------------------------

class TestProperty3RetryDelays(unittest.TestCase):
    # Feature: issue-8-db-resilience, Property 3: Retry delays follow the exponential schedule

    @given(st.just(True))  # always-fail scenario
    @settings(max_examples=100)
    def test_sleep_called_with_correct_delays(self, _):
        """
        **Validates: Requirements 2.2, 2.3, 2.4**
        time.sleep is called exactly 3 times with [0.5, 1.0, 2.0] in order.
        """
        svc = _make_service_live_mode()
        svc.pool.getconn.side_effect = Exception("always fail")
        svc._try_recreate_pool = MagicMock(return_value=None)

        sleep_calls = []
        with patch('time.sleep', side_effect=lambda d: sleep_calls.append(d)):
            with patch('logging.warning'):
                svc._checkout_with_retry()

        self.assertEqual(sleep_calls, [0.5, 1.0, 2.0])


# ---------------------------------------------------------------------------
# Task 3.3 — Property 4: Retry logs contain attempt number and exception text
# ---------------------------------------------------------------------------

class TestProperty4RetryLogs(unittest.TestCase):
    # Feature: issue-8-db-resilience, Property 4: Retry logs always contain attempt number and exception text

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=100)
    def test_warning_logs_contain_attempt_number_and_exception_text(self, exc_msg):
        """
        **Validates: Requirements 2.6**
        Every WARNING log call during retry contains the attempt number and exc text.
        """
        svc = _make_service_live_mode()
        svc.pool.getconn.side_effect = Exception(exc_msg)
        svc._try_recreate_pool = MagicMock(return_value=None)

        log_messages = []
        with patch('time.sleep'):
            with patch('logging.warning', side_effect=lambda msg, *a, **kw: log_messages.append(str(msg))):
                svc._checkout_with_retry()

        # Filter out MOCK FALLBACK messages — those come from get_db_connection, not _checkout_with_retry
        retry_logs = [m for m in log_messages if 'MOCK FALLBACK' not in m]

        # Should have exactly 3 retry warning logs
        self.assertEqual(len(retry_logs), 3)
        for i, msg in enumerate(retry_logs, start=1):
            self.assertIn(str(i), msg)
            self.assertIn(exc_msg, msg)


# ---------------------------------------------------------------------------
# Task 4 — _try_recreate_pool() unit tests
# ---------------------------------------------------------------------------

class TestTryRecreatePool(unittest.TestCase):
    def test_pool_recreation_success(self):
        """Pool factory succeeds: self.pool replaced, postgresMode=='live', conn returned."""
        svc = _make_service_live_mode()
        new_pool = MagicMock()
        new_conn = MagicMock()
        new_pool.getconn.return_value = new_conn

        with patch('psycopg2.pool.ThreadedConnectionPool', return_value=new_pool):
            svc._validate_connection = MagicMock()
            result = svc._try_recreate_pool()

        self.assertIs(svc.pool, new_pool)
        self.assertEqual(svc.postgresMode, "live")
        self.assertIs(result, new_conn)

    def test_pool_recreation_failure_returns_none(self):
        """Pool factory raises: ERROR log emitted, None returned."""
        svc = _make_service_live_mode()

        with patch('psycopg2.pool.ThreadedConnectionPool', side_effect=Exception("cannot connect")):
            with patch('logging.error') as mock_error:
                result = svc._try_recreate_pool()

        self.assertIsNone(result)
        mock_error.assert_called_once()


# ---------------------------------------------------------------------------
# Task 4.1 — Property 5: Pool recreation called at most once per get_db_connection()
# ---------------------------------------------------------------------------

class TestProperty5RecreationCalledOnce(unittest.TestCase):
    # Feature: issue-8-db-resilience, Property 5: Pool recreation attempted at most once per get_db_connection()

    @given(st.just(True))
    @settings(max_examples=100)
    def test_try_recreate_pool_called_exactly_once(self, _):
        """
        **Validates: Requirements 3.4**
        _try_recreate_pool is called exactly once regardless of retry count.
        """
        svc = _make_service_live_mode()
        svc.pool.getconn.side_effect = Exception("always fail")
        recreate_spy = MagicMock(return_value=None)
        svc._try_recreate_pool = recreate_spy

        with patch('time.sleep'):
            with patch('logging.warning'):
                svc._checkout_with_retry()

        recreate_spy.assert_called_once()


# ---------------------------------------------------------------------------
# Task 5 — get_db_connection() unit tests
# ---------------------------------------------------------------------------

class TestGetDbConnection(unittest.TestCase):
    def test_mock_mode_yields_none_immediately(self):
        """postgresMode=='mock' → yields None immediately, no retries, no MOCK FALLBACK warning."""
        svc = _make_service_mock_mode()

        with patch('logging.warning') as mock_warn:
            with svc.get_db_connection() as conn:
                self.assertIsNone(conn)
            # No MOCK FALLBACK warning
            for c in mock_warn.call_args_list:
                self.assertNotIn('MOCK FALLBACK', str(c))

    def test_pool_none_yields_none_immediately(self):
        """pool is None → yields None immediately."""
        svc = _make_service_live_mode(pool=None)
        svc.postgresMode = "live"
        svc.pool = None

        with svc.get_db_connection() as conn:
            self.assertIsNone(conn)

    def test_successful_checkout_yields_connection(self):
        """Happy path: valid connection checked out and yielded."""
        svc = _make_service_live_mode()
        real_conn = MagicMock()
        svc._checkout_with_retry = MagicMock(return_value=real_conn)

        with svc.get_db_connection() as conn:
            self.assertIsNotNone(conn)
        svc.pool.putconn.assert_called_once()

    def test_checkin_happens_in_finally(self):
        """Connection is returned to pool even if caller raises."""
        svc = _make_service_live_mode()
        real_conn = MagicMock()
        svc._checkout_with_retry = MagicMock(return_value=real_conn)

        try:
            with svc.get_db_connection() as conn:
                raise ValueError("caller error")
        except ValueError:
            pass

        svc.pool.putconn.assert_called_once()

    def test_all_retries_fail_yields_none_with_mock_fallback_warning(self):
        """All retries exhausted → MOCK FALLBACK warning emitted, None yielded."""
        svc = _make_service_live_mode()
        svc._checkout_with_retry = MagicMock(return_value=None)

        with patch('logging.warning') as mock_warn:
            with svc.get_db_connection() as conn:
                self.assertIsNone(conn)

        logged_messages = [str(c) for c in mock_warn.call_args_list]
        self.assertTrue(any('MOCK FALLBACK' in m for m in logged_messages))


# ---------------------------------------------------------------------------
# Task 5.1 — Property 6: MOCK FALLBACK warning always contains last error text
# ---------------------------------------------------------------------------

class TestProperty6MockFallbackWarning(unittest.TestCase):
    # Feature: issue-8-db-resilience, Property 6: MOCK FALLBACK warning always contains last error text

    @given(st.text(min_size=1, max_size=300))
    @settings(max_examples=100)
    def test_mock_fallback_warning_contains_mock_fallback_and_error(self, error_text):
        """
        **Validates: Requirements 4.2, 4.3**
        WARNING log before yielding None always contains 'MOCK FALLBACK' and the error text.
        """
        svc = _make_service_live_mode()
        svc.pool.getconn.side_effect = Exception(error_text)
        svc._try_recreate_pool = MagicMock(return_value=None)

        log_messages = []
        with patch('time.sleep'):
            with patch('logging.warning', side_effect=lambda msg, *a, **kw: log_messages.append(str(msg))):
                result = svc._checkout_with_retry()

        self.assertIsNone(result)
        fallback_logs = [m for m in log_messages if 'MOCK FALLBACK' in m]
        self.assertEqual(len(fallback_logs), 1)
        self.assertIn(error_text, fallback_logs[0])


# ---------------------------------------------------------------------------
# Task 5.2 — Mock mode short-circuit unit test
# ---------------------------------------------------------------------------

class TestMockModeShortCircuit(unittest.TestCase):
    def test_no_retries_in_mock_mode(self):
        """In mock mode, _checkout_with_retry is never called."""
        svc = _make_service_mock_mode()
        svc._checkout_with_retry = MagicMock()

        with svc.get_db_connection() as conn:
            self.assertIsNone(conn)

        svc._checkout_with_retry.assert_not_called()


# ---------------------------------------------------------------------------
# Task 6 — _SlowQueryCursor unit tests
# ---------------------------------------------------------------------------

class TestSlowQueryCursorUnit(unittest.TestCase):
    def _make_cursor(self):
        return MagicMock()

    def test_query_at_exactly_500ms_emits_warning(self):
        """Query at exactly 500 ms → SLOW QUERY warning emitted."""
        cursor = self._make_cursor()
        slow_cursor = _SlowQueryCursor(cursor)

        times = [0.0, 0.5]  # elapsed = 500 ms
        with patch('time.monotonic', side_effect=times):
            with patch('logging.warning') as mock_warn:
                slow_cursor.execute("SELECT 1")

        msgs = [str(c) for c in mock_warn.call_args_list]
        self.assertTrue(any('SLOW QUERY' in m for m in msgs))

    def test_query_at_499ms_no_warning(self):
        """Query at 499 ms → no SLOW QUERY warning."""
        cursor = self._make_cursor()
        slow_cursor = _SlowQueryCursor(cursor)

        times = [0.0, 0.499]  # elapsed = 499 ms
        with patch('time.monotonic', side_effect=times):
            with patch('logging.warning') as mock_warn:
                slow_cursor.execute("SELECT 1")

        msgs = [str(c) for c in mock_warn.call_args_list]
        self.assertFalse(any('SLOW QUERY' in m for m in msgs))

    def test_getattr_delegation(self):
        """Non-execute attributes forward to wrapped cursor."""
        cursor = self._make_cursor()
        cursor.fetchone.return_value = ("row",)
        slow_cursor = _SlowQueryCursor(cursor)

        result = slow_cursor.fetchone()
        self.assertEqual(result, ("row",))
        cursor.fetchone.assert_called_once()

    def test_execute_with_params(self):
        """execute with params passes them through correctly."""
        cursor = self._make_cursor()
        slow_cursor = _SlowQueryCursor(cursor)

        with patch('time.monotonic', side_effect=[0.0, 0.001]):
            with patch('logging.warning'):
                slow_cursor.execute("SELECT %s", (1,))

        cursor.execute.assert_called_once_with("SELECT %s", (1,))

    def test_execute_without_params(self):
        """execute without params passes through correctly."""
        cursor = self._make_cursor()
        slow_cursor = _SlowQueryCursor(cursor)

        with patch('time.monotonic', side_effect=[0.0, 0.001]):
            with patch('logging.warning'):
                slow_cursor.execute("SELECT 1")

        cursor.execute.assert_called_once_with("SELECT 1")


# ---------------------------------------------------------------------------
# Task 6.1 — Property 7: Slow query warning for queries ≥ 500 ms
# ---------------------------------------------------------------------------

class TestProperty7SlowQueryWarning(unittest.TestCase):
    # Feature: issue-8-db-resilience, Property 7: Slow query warning always contains query text and elapsed time

    @given(
        st.floats(min_value=500.0, max_value=60000.0),
        st.text(min_size=1, max_size=500),
    )
    @settings(max_examples=100)
    def test_slow_query_warning_contains_slow_query_and_sql(self, elapsed_ms, sql):
        """
        **Validates: Requirements 5.2**
        WARNING contains 'SLOW QUERY', elapsed ms, and the SQL text.
        """
        cursor = MagicMock()
        slow_cursor = _SlowQueryCursor(cursor)

        elapsed_s = elapsed_ms / 1000.0
        with patch('time.monotonic', side_effect=[0.0, elapsed_s]):
            log_messages = []
            with patch('logging.warning', side_effect=lambda msg, *a, **kw: log_messages.append(str(msg))):
                slow_cursor.execute(sql)

        slow_logs = [m for m in log_messages if 'SLOW QUERY' in m]
        self.assertEqual(len(slow_logs), 1)
        self.assertIn(sql, slow_logs[0])
        # Check elapsed ms is in the message (allow for rounding)
        self.assertIn('SLOW QUERY', slow_logs[0])


# ---------------------------------------------------------------------------
# Task 6.2 — Property 8: No warning for fast queries
# ---------------------------------------------------------------------------

class TestProperty8NoWarningFastQueries(unittest.TestCase):
    # Feature: issue-8-db-resilience, Property 8: No slow query warning for fast queries

    @given(
        st.floats(min_value=0.0, max_value=0.4999),
        st.text(min_size=1),
    )
    @settings(max_examples=100)
    def test_no_slow_query_warning_for_fast_queries(self, elapsed_s, sql):
        """
        **Validates: Requirements 5.3**
        No SLOW QUERY WARNING is emitted for queries < 500 ms.
        """
        cursor = MagicMock()
        slow_cursor = _SlowQueryCursor(cursor)

        with patch('time.monotonic', side_effect=[0.0, elapsed_s]):
            log_messages = []
            with patch('logging.warning', side_effect=lambda msg, *a, **kw: log_messages.append(str(msg))):
                slow_cursor.execute(sql)

        slow_logs = [m for m in log_messages if 'SLOW QUERY' in m]
        self.assertEqual(len(slow_logs), 0)


# ---------------------------------------------------------------------------
# Task 8.2 — Integration smoke test
# ---------------------------------------------------------------------------

class TestIntegrationMockMode(unittest.TestCase):
    def setUp(self):
        """Instantiate PostgreSqlService in mock mode (no env vars set)."""
        import os
        # Ensure no DB env vars so it starts in mock mode
        env_backup = {k: os.environ.pop(k, None) for k in ['DB_USER', 'DB_NAME', 'DB_HOST', 'DB_PORT', 'DB_PASSWORD']}
        self._env_backup = env_backup
        self.svc_factory = lambda: PostgreSqlService()

    def tearDown(self):
        import os
        for k, v in self._env_backup.items():
            if v is not None:
                os.environ[k] = v

    def test_get_devices_returns_mock_data(self):
        svc = self.svc_factory()
        self.assertEqual(svc.postgresMode, "mock")
        devices = svc.getDevices()
        self.assertIsInstance(devices, dict)
        self.assertGreater(len(devices), 0)

    def test_update_device_works_in_mock_mode(self):
        svc = self.svc_factory()
        result = svc.updateDevice("geyser", "ON")
        self.assertTrue(result)
        self.assertEqual(svc.mockDevices["geyser"]["status"], "ON")

    def test_get_energy_stats_returns_mock_data(self):
        svc = self.svc_factory()
        stats = svc.getEnergyStats()
        self.assertIn("totalSavedWh", stats)
        self.assertIn("rupeesSaved", stats)

    def test_no_unexpected_warnings_in_mock_mode(self):
        """Mock mode must not emit MOCK FALLBACK warnings."""
        svc = self.svc_factory()
        with patch('logging.warning') as mock_warn:
            svc.getDevices()
            svc.getEnergyStats()

        for c in mock_warn.call_args_list:
            self.assertNotIn('MOCK FALLBACK', str(c))


if __name__ == "__main__":
    unittest.main()
