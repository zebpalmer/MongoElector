import logging
import threading
from time import sleep

from pymongo.errors import OperationFailure

from mongoelector.locker import AcquireTimeout, LockExists, MongoLocker, _utcnow

log = logging.getLogger(__name__)


class MongoLeaderElector:
    """Coordinates distributed leader election using MongoDB-based locking.

    Runs a background thread that periodically attempts to acquire leadership
    and invokes callbacks on state transitions.

    Can be used as a context manager::

        with MongoLeaderElector("my-service", db, on_leader=start_work) as elector:
            # elector is running
            while elector.running:
                sleep(1)
        # elector is stopped, leadership released
    """

    def __init__(
        self,
        key,
        db,
        *,
        ttl=15,
        on_leader=None,
        on_leader_loss=None,
        on_loop=None,
        app_version=None,
        report_status=True,
    ):
        self._poll_lock = threading.Lock()
        self._ts_poll = None
        self._shutdown = False
        self._was_leader = False
        self._app_version = app_version
        self._report_status = report_status
        self._elector_thread = None
        self.key = key
        self.db = db
        self.ttl = ttl
        self.callback_on_leader = on_leader
        self.callback_on_leader_loss = on_leader_loss
        self.callback_on_loop = on_loop

        self._status_collection = db["elector.leader_status"]
        try:
            self._status_collection.create_index("timestamp", expireAfterSeconds=int(ttl))
        except OperationFailure:
            self._status_collection.drop_indexes()
            self._status_collection.create_index("timestamp", expireAfterSeconds=int(ttl))
        self._status_collection.create_index("key")

        self.mlock = MongoLocker(key, db, dbcollection="elector.locks", ttl=ttl, timeparanoid=True)

    def __repr__(self):
        leader = "leader" if self.is_leader else "follower"
        running = "running" if self.running else "stopped"
        return f"MongoLeaderElector(key={self.key!r}, {leader}, {running}, uuid={self.mlock.uuid!r})"

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False

    def start(self, blocking=False):
        """Start the elector background thread.

        Args:
            blocking: If True, block until the elector thread exits.
        """
        self._shutdown = False
        self._elector_thread = _LeaderElectorThread(self)
        self._elector_thread.start()
        if blocking:
            self._elector_thread.join()

    def stop(self):
        """Stop the elector thread and release leadership."""
        self._shutdown = True
        if self._elector_thread and threading.current_thread() is not self._elector_thread:
            self._elector_thread.join()
        self.release()

    @property
    def running(self):
        return self._elector_thread.is_alive() if self._elector_thread else False

    @property
    def is_leader(self):
        return self.mlock.owned()

    @property
    def leader_exists(self):
        return self.mlock.locked()

    def poll(self):
        """Execute one poll cycle: touch/renew if leader, attempt acquire if not."""
        with self._poll_lock:
            self._ts_poll = _utcnow()

            if self.mlock.owned():
                self._was_leader = True
                self.mlock.touch()
            elif self._was_leader:
                self._was_leader = False
                self._fire_callback(self.callback_on_leader_loss, "on_leader_loss")

            if not self.leader_exists and not self._shutdown:
                try:
                    self.mlock.acquire(blocking=False)
                except (LockExists, AcquireTimeout):
                    pass
                else:
                    if self.mlock.owned():
                        self._was_leader = True
                        self._fire_callback(self.callback_on_leader, "on_leader")

            if self._report_status:
                self._report_node_status()

            self._fire_callback(self.callback_on_loop, "on_loop")

    def _fire_callback(self, callback, name):
        if callback:
            try:
                callback()
            except Exception:
                log.exception("Error in %s callback", name)

    def _report_node_status(self):
        status = self.node_status
        self._status_collection.update_one({"_id": status["_id"]}, {"$set": status}, upsert=True)

    @property
    def cluster_detail(self):
        data = list(self._status_collection.find({"key": self.key}, {"_id": 0}).sort("timestamp", -1))
        return {
            "member_detail": data,
            "leader": _parse_leader(data),
            "timestamp": _utcnow(),
        }

    @property
    def node_status(self):
        status = self.mlock.status
        status["_id"] = status["uuid"]
        status["is_leader"] = self.is_leader
        status["elector_running"] = self.running
        status["last_poll"] = self._ts_poll
        if self._app_version:
            status["app_version"] = self._app_version
        return status

    def release(self):
        """Release leadership and fire the on_leader_loss callback if applicable."""
        with self._poll_lock:
            self.mlock.release()
            if self._was_leader:
                self._was_leader = False
                self._fire_callback(self.callback_on_leader_loss, "on_leader_loss during release")

    @property
    def poll_wait(self):
        """Seconds between poll cycles. Leaders poll at half the TTL."""
        return self.ttl / 2.0 if self._was_leader else self.ttl


class _LeaderElectorThread(threading.Thread):
    """Background daemon thread that drives the elector poll loop."""

    def __init__(self, elector):
        super().__init__(daemon=True)
        self.elector = elector

    def run(self):
        while not self.elector._shutdown:
            try:
                self.elector.poll()
            except Exception:
                log.exception("Elector poll error")
            finally:
                sleep(self.elector.poll_wait)


def _parse_leader(data):
    for entry in data:
        if entry.get("is_leader"):
            return {
                "host": entry.get("host"),
                "process_id": entry.get("pid"),
                "uuid": entry.get("uuid"),
            }
    return None
