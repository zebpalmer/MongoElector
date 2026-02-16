import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from mongoelector import LockExists, MongoLocker


def test_init_and_invalid_args(db):
    MongoLocker("testinit", db, timeparanoid=False)
    with pytest.raises(TypeError):
        MongoLocker(None, None)
    with pytest.raises(ValueError):
        MongoLocker("testinit", db, ttl="not-an-int")
    with pytest.raises(ValueError):
        MongoLocker("", db)
    with pytest.raises(ValueError):
        MongoLocker("testinit", db, ttl=-1)


def test_lock_cycle(db):
    lock = MongoLocker("testcycle", db, timeparanoid=False)
    if lock.locked():
        lock.release(force=True)

    lock.acquire()
    assert lock.locked()
    assert lock.owned()
    lock.release()
    assert not lock.owned()
    assert not lock.locked()

    lock.acquire()
    lock.release(force=False)
    assert not lock.locked()


def test_time_paranoia_mocked(db):
    with patch("mongoelector.locker.MongoLocker._verifytime", return_value=True):
        lock = MongoLocker("testparanoia", db, timeparanoid=True)
        assert lock._verifytime() is True


def test_force_release(db):
    l1 = MongoLocker("testrelease", db, timeparanoid=False)
    l2 = MongoLocker("testrelease", db, timeparanoid=False)
    l1.acquire()

    with pytest.raises(LockExists):
        l2.acquire(blocking=False)

    l2.release()
    assert l1.locked()
    assert l1.owned()

    l2.release(force=True)
    assert not l1.locked()
    assert not l1.owned()


def test_acquire_retry_logic():
    fn = MongoLocker._acquireretry
    now = datetime.now(timezone.utc)

    # blocking=False with timeout is invalid
    with pytest.raises(ValueError):
        fn(False, now, 10, 0)

    # blocking=True with generous timeout allows retries
    assert fn(True, now, 10, 1)
    assert fn(True, now, 10, 0)

    # blocking=True with expired timeout
    past = now - timedelta(minutes=1)
    assert not fn(True, past, 5, 10)

    # blocking=False only allows count==0
    assert fn(False, now, None, 0)
    assert not fn(False, now, None, 1)


def test_force_acquire(db):
    a = MongoLocker("testforce", db, timeparanoid=False)
    b = MongoLocker("testforce", db, timeparanoid=False)
    a.acquire()
    assert a.owned()

    b.acquire(force=True)
    assert b.owned()
    assert not a.owned()

    a.release()
    b.release()
    assert not a.locked()
    assert not b.locked()


def test_touch_updates_expiration(db):
    lock = MongoLocker("testtouch", db, timeparanoid=False)
    lock.acquire()
    start_ts = lock.ts_expire.replace(tzinfo=None) if lock.ts_expire.tzinfo else lock.ts_expire
    time.sleep(1)
    updated = lock.touch()
    assert updated
    end_ts = lock.ts_expire.replace(tzinfo=None) if lock.ts_expire.tzinfo else lock.ts_expire
    assert end_ts > start_ts


def test_status_property(db):
    lock = MongoLocker("teststatus", db, timeparanoid=False)
    status = lock.status

    assert isinstance(status["pid"], int)
    assert status["lock_created"] is None
    assert status["lock_expires"] is None
    assert status["lock_owned"] is False

    lock.acquire()
    status = lock.status
    assert status["lock_owned"] is True
    assert isinstance(status["lock_created"], datetime)
    assert isinstance(status["lock_expires"], datetime)
