import uuid
from os import getpid
from socket import getfqdn
from time import sleep
from datetime import datetime, timedelta
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, OperationFailure


class LockExists(Exception):
    """Raise when a lock exists"""
    pass


class AcquireTimeout(Exception):
    """Raise when can't get lock"""


class MongoLocker(object):
    """
    Distributed lock object backed by MongoDB.

    Intended to mimic standard lib Lock object as much as
    reasonable. This object is used by MongoElector, but
    is perfectly happy being used as a standalone distributed
    locking object.

    """

    def __init__(self, key, db,
                 dbcollection='mongolocker', ttl=600, timeparanoid=True):
        """
        :param key: Name of distributed lock
        :type key: str
        :param dbconn: Pymongo client connection to mongodb
        :type dbconn: PyMongo db connection
        :param dbname: name of database (defaults to 'mongoelector')
        :type dbname: str
        :param dbname: name of collection (defaults to 'mongolocker')
        :type dbname: str
        :param ttl: Lock will expire (ttl seconds) after acquired unless renewed or released
        :type ttl: int
        :param timeparanoid: Sanity check to ensure local server time matches mongodb server time (utc)
        :type timeparanoid: bool
        """
        self.uuid = str(uuid.uuid4())
        self.host = getfqdn()
        self.pid = getpid()
        self.ts_expire = None
        self.timeparanoid = timeparanoid
        self.dbcollection = dbcollection
        self._sanetime = None
        self._maxoffset = 0.5
        self._ttl_indexed = None
        self.database = db
        if key and db is not None:
            self.key = key
            self.collection = getattr(self.database, dbcollection)
        else:
            raise ValueError("must provide key name and pyongo database connection")
        if ttl:
            if isinstance(ttl, int):
                self._ttl = ttl
                self._setup_ttl()
            else:
                raise ValueError("ttl must be int() seconds")

    @property
    def status(self):
        lock_created = None
        lock_expires = None
        timestamp = datetime.utcnow()
        current = self.get_current()
        mine = False
        if current:
            mine = bool(current.get('uuid', False) == self.uuid)
            if mine:  # Only include these details if lock is owned (prevent races)
                lock_created = current['ts_created']
                lock_expires = current['ts_expire']
        return {'uuid': self.uuid,
                'key': self.key,
                'ttl': self._ttl,
                'timestamp': timestamp,
                'host': self.host,
                'pid': self.pid,
                'lock_owned': mine,
                'lock_created': lock_created,
                'lock_expires': lock_expires}

    def _setup_ttl(self):
        try:
            self.collection.create_index('ts_expire', expireAfterSeconds=self._ttl)
        except OperationFailure:
            self.collection.drop_indexes()
            self.collection.create_index('ts_expire', expireAfterSeconds=self._ttl)
        self._ttl_indexed = True

    @staticmethod
    def _acquireretry(blocking, start, timeout, count):
        """Determine if a retry is appropriate"""
        if blocking is False and timeout:
            raise ValueError("Blocking can't be false with a timeout set")
        if blocking is False:
            if count > 0:
                return False
            else:
                return True
        else:  # blocking true
            if count == 0:
                return True
            if (datetime.utcnow() - start) > timedelta(seconds=timeout):
                return False
            else:
                return True

    def _verifytime(self):
        """verify database server's time matches local machine time"""
        # TODO: decide if this is still needed, fix test if so
        
        # if self._sanetime and self._sanetime > datetime.utcnow() - timedelta(minutes=10):
        #     return True
        # else:
        #     mongotime = self.database.command('serverStatus')['localTime']
        #     pytime = datetime.utcnow()
        #     delta = pytime - mongotime
        #     offset = abs(delta.total_seconds())
        #     if offset > self._maxoffset:
        #         raise Exception("Time offset compared to mongodb is too high {}".format(round(offset, 2)))
        #     else:
        #         self._sanetime = datetime.utcnow()
        #     return True

    def acquire(self, blocking=True, timeout=None, step=0.25, force=False):
        """
        Attempts to acquire the lock, will block and retry
        indefinitely by default. Can be configured not to block,
        or to have a timeout. You can also force the acquisition
        if you have a really good reason to do so.

        :param blocking: If true (default), will wait until lock is acquired.
        :type blocking: bool
        :param timeout: blocking acquire will fail after timeout in seconds if the lock hasn't been acquired yet.
        :type timeout: int
        :param step: delay between acquire attempts
        :type step: float or int
        :param force: CAUTION: will forcibly take ownership of the lock
        :type force: bool


        """
        if self.timeparanoid is True:
            self._verifytime()
        count = 0
        start = datetime.utcnow()
        while self._acquireretry(blocking, start, timeout, count):
            count += 1
            try:
                created = datetime.utcnow()
                self.ts_expire = created + timedelta(seconds=int(self._ttl))
                payload = {'_id': self.key,
                           'locked': True,
                           'host': self.host,
                           'uuid': self.uuid,
                           'pid': self.pid,
                           'ts_created': created,
                           'ts_expire': self.ts_expire}
                if force:
                    res = self.collection.find_one_and_replace({'_id': self.key}, payload, new=True)
                else:
                    res = self.collection.insert_one(payload)
                return res
            except DuplicateKeyError:
                existing = self.collection.find_one({'_id': self.key})
                countdown = (datetime.utcnow() - existing['ts_expire']).total_seconds()
                if not blocking:
                    raise LockExists('{} owned by {} pid {}, expires in {}s'.format(self.key,
                                                                                    existing['host'],
                                                                                    existing.get('pid', '?'),
                                                                                    countdown))
                else:
                    sleep(step)
        raise AcquireTimeout("Timeout reached, lock not acquired")

    def locked(self):
        """
        Returns current status of the lock, but does not indicate if
        the current instance has ownership or not. (for that, use 'self.owned()')
        This is a 'look before you leap' option. For example, it can be used
        to ensure that some process is owns the lock and is doing the associated work.
        Obviously this method does not guarantee that the current instance will be
        successful in obtaining the lock on a subsequent acquire.

        :return: Lock status
        :rtype: bool
        """
        locked = False
        res = self.collection.find_one({'_id': self.key, 'ts_expire': {'$gt': datetime.utcnow()}})
        if res:
            locked = res['locked']
        return locked

    def owned(self):
        """
        Determines if self is the owner of the lock object.
        This verifies the instance uuid matches the
        uuid of the lock record in the db.

        :return: Owner status
        :rtype: bool
        """
        return bool(self.collection.find_one({'_id': self.key,
                                       'uuid': self.uuid,
                                       'locked': True,
                                       'ts_expire': {'$gt': datetime.utcnow()}}))

    def get_current(self):
        """
        Returns the current (valid) lock object from the database,
        regardless of which instance it is owned by.
        """
        return self.collection.find_one({'_id': self.key,
                                  'locked': True,
                                  'ts_expire': {'$gt': datetime.utcnow()}})

    def release(self, force=False):
        """
        releases lock if owned by the current instance.

        :param force: CAUTION: Forces the release to happen,
        even if the local instance isn't the lock owner.
        :type force: bool
        """
        if force:
            query = {'_id': self.key}
        else:
            query = {'_id': self.key,
                     'uuid': self.uuid}
        self.collection.delete_many(query)

    def touch(self):
        """
        Renews lock expiration timestamp

        :return: new expiration timestamp
        :rtype: datetime
        """
        ts_expire = datetime.utcnow() + timedelta(seconds=int(self._ttl))
        result = self.collection.find_one_and_update({'_id': self.key,
                                               'uuid': self.uuid,
                                               'locked': True,
                                               'ts_expire': {'$gt': datetime.utcnow()}},
                                              {'$set': {'ts_expire': ts_expire}},
                                              return_document=ReturnDocument.AFTER)
        if result:
            self.ts_expire = result['ts_expire']
            return self.ts_expire
        else:
            return False
