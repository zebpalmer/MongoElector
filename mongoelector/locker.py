import uuid
from datetime import datetime, timedelta, timezone
from os import getpid
from socket import getfqdn
from time import sleep

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, OperationFailure


def _utcnow():
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(tz=timezone.utc)


class LockExists(Exception):
    """Raised when attempting a non-blocking acquire on an existing lock."""


class AcquireTimeout(Exception):
    """Raised when lock acquisition times out."""


class TimeOffsetError(Exception):
    """Raised when the clock offset between this host and MongoDB is too high."""


class MongoLocker:
    """Distributed lock backed by MongoDB.

    Mimics the standard library Lock interface where reasonable.
    Used internally by MongoLeaderElector, but works as a standalone
    distributed locking primitive.

    Can be used as a context manager::

        with MongoLocker("my-resource", db, ttl=30) as lock:
            # lock is held
            pass
        # lock is released
    """

    def __init__(self, key, db, *, dbcollection="mongolocker", ttl=600, timeparanoid=True, maxoffset=0.5):
        if not hasattr(db, "create_collection"):
            raise TypeError("Must pass a pymongo Database instance, not a bare MongoClient")
        if not key:
            raise ValueError("Must provide a non-empty lock key")
        if not isinstance(ttl, (int, float)) or ttl <= 0:
            raise ValueError("ttl must be a positive number (seconds)")

        self.uuid = str(uuid.uuid4())
        self.host = getfqdn()
        self.pid = getpid()
        self.ts_expire = None
        self.timeparanoid = timeparanoid
        self.key = key
        self.database = db
        self.collection = db[dbcollection]
        self._ttl = ttl
        self._sanetime = None
        self._maxoffset = maxoffset

        self._setup_ttl()

    def __repr__(self):
        return f"MongoLocker(key={self.key!r}, uuid={self.uuid!r}, host={self.host!r}, owned={self.owned()})"

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False

    @property
    def status(self):
        current = self.get_current()
        mine = False
        lock_created = None
        lock_expires = None
        if current:
            mine = current.get("uuid") == self.uuid
            if mine:
                lock_created = current["ts_created"]
                lock_expires = current["ts_expire"]
        return {
            "uuid": self.uuid,
            "key": self.key,
            "ttl": self._ttl,
            "timestamp": _utcnow(),
            "host": self.host,
            "pid": self.pid,
            "lock_owned": mine,
            "lock_created": lock_created,
            "lock_expires": lock_expires,
        }

    def _setup_ttl(self):
        try:
            self.collection.create_index("ts_expire", expireAfterSeconds=0)
        except OperationFailure:
            self.collection.drop_indexes()
            self.collection.create_index("ts_expire", expireAfterSeconds=0)

    @staticmethod
    def _acquireretry(blocking, start, timeout, count):
        if not blocking and timeout:
            raise ValueError("blocking=False is incompatible with a timeout")
        if not blocking:
            return count == 0
        if timeout is None:
            return True
        return (_utcnow() - start) <= timedelta(seconds=timeout)

    def _verifytime(self):
        now = _utcnow()
        if self._sanetime and self._sanetime > now - timedelta(minutes=10):
            return True
        mongotime = self.database.command("serverStatus")["localTime"]
        offset = abs((now - mongotime).total_seconds())
        if offset > self._maxoffset:
            raise TimeOffsetError(f"Clock offset vs MongoDB is too high: {round(offset, 2)}s")
        self._sanetime = now
        return True

    def acquire(self, blocking=True, timeout=None, step=0.25, force=False):
        """Acquire the distributed lock.

        Args:
            blocking: If True, wait until the lock is available. If False, raise LockExists immediately.
            timeout: Maximum seconds to wait when blocking. None means wait forever (requires blocking=True).
            step: Seconds between retry attempts when blocking.
            force: If True, forcibly take the lock from any current holder.

        Returns:
            True if the lock was acquired.

        Raises:
            LockExists: Lock is held and blocking=False.
            AcquireTimeout: Timed out waiting for the lock.
        """
        if self.timeparanoid:
            self._verifytime()
        count = 0
        start = _utcnow()
        while self._acquireretry(blocking, start, timeout, count):
            count += 1
            try:
                created = _utcnow()
                self.ts_expire = created + timedelta(seconds=self._ttl)
                payload = {
                    "_id": self.key,
                    "locked": True,
                    "host": self.host,
                    "uuid": self.uuid,
                    "pid": self.pid,
                    "ts_created": created,
                    "ts_expire": self.ts_expire,
                }
                if force:
                    self.collection.find_one_and_replace(
                        {"_id": self.key}, payload, upsert=True, return_document=ReturnDocument.AFTER
                    )
                else:
                    self.collection.insert_one(payload)
                return True
            except DuplicateKeyError:
                existing = self.collection.find_one({"_id": self.key})
                if existing and not blocking:
                    raise LockExists(f"{self.key} owned by {existing['host']} pid {existing.get('pid', '?')}") from None
                sleep(step)
        raise AcquireTimeout("Timeout reached, lock not acquired")

    def locked(self):
        """Return True if the lock is currently held by anyone."""
        res = self.collection.find_one({"_id": self.key, "ts_expire": {"$gt": _utcnow()}})
        return bool(res and res.get("locked"))

    def owned(self):
        """Return True if the lock is currently held by this instance."""
        return bool(
            self.collection.find_one(
                {
                    "_id": self.key,
                    "uuid": self.uuid,
                    "locked": True,
                    "ts_expire": {"$gt": _utcnow()},
                }
            )
        )

    def get_current(self):
        """Return the current lock document, or None if no active lock."""
        return self.collection.find_one(
            {
                "_id": self.key,
                "locked": True,
                "ts_expire": {"$gt": _utcnow()},
            }
        )

    def release(self, force=False):
        """Release the lock. If force=True, release regardless of ownership."""
        query = {"_id": self.key} if force else {"_id": self.key, "uuid": self.uuid}
        self.collection.delete_many(query)

    def touch(self):
        """Renew the lock's TTL. Returns the new expiration time, or None if the lock is not owned."""
        ts_expire = _utcnow() + timedelta(seconds=self._ttl)
        result = self.collection.find_one_and_update(
            {
                "_id": self.key,
                "uuid": self.uuid,
                "locked": True,
                "ts_expire": {"$gt": _utcnow()},
            },
            {"$set": {"ts_expire": ts_expire}},
            return_document=ReturnDocument.AFTER,
        )
        if result:
            self.ts_expire = result["ts_expire"]
            return self.ts_expire
        return None
