import uuid
from socket import getfqdn
from time import sleep
from datetime import datetime, timedelta
from pymongo.errors import DuplicateKeyError

class LockExists(Exception):
    '''Raise when a lock exists'''
    pass

class AcquireTimeout(Exception):
    '''Raise when can't get lock'''

class MongoLocker(object):
    '''
    Distributed lock object backed by MongoDB.

    Inteded to mimic standard lib Lock object as much as
    reasonable. This object is used by MongoElector, but
    is perfectly happy being used as a standalone distributed
    locking object.

    '''

    def __init__(self, key, dbconn, dbname='mongoelector',
                 dbcollection = 'mongolocker', ttl=600, timeparanoid=1):
        '''
        :param key: Name of distributed lock
        :type key: str
        :param dbconn: Pymongo client connection to mongodb collection
        :type dbconn: PyMongo db connection
        :param dbname: name of database (defaults to 'mongoelector')
        :type dbname: str
        :param dbname: name of collection (defaults to 'mongoelector')
        :type dbname: str
        :param ttl: Lock will expire (ttl seconds) after acquired unless renewed or released
        :type ttl: int
        '''
        self.uuid = str(uuid.uuid4())
        self.host = getfqdn()
        self.ts_expire = None
        self.ts_created = None
        self.timeparanoid = timeparanoid
        self.dbname = dbname
        self.dbcollection = dbcollection
        self._sanetime = None
        self._maxoffset = 0.5
        if key and dbconn:
            self.key = key
            self._db = getattr(getattr(dbconn, dbname), dbcollection)
            self._dbconn = dbconn
        else:
            raise ValueError("must provide key name and pyongo connection")
        if ttl:
            if isinstance(ttl, int):
                self._ttl = ttl
            else:
                raise ValueError("ttl must be int() seconds")

    @staticmethod
    def _acquireretry(blocking, start, timeout, count):
        if blocking is False and count > 0:
            return False
        if blocking is True and count == 0:
            return True
        if timeout:
            if (datetime.utcnow() - start) > timedelta(seconds=timeout):
                return False
            else:
                return True

    def _verifytime(self):
        timeok = True
        serverlocal = getattr(self._dbconn, self.dbname).command('serverStatus')['localTime']
        pytime = datetime.utcnow()
        delta = pytime - serverlocal
        offset = abs(delta.total_seconds())
        if offset > self._maxoffset:
            timeok = False
        return timeok, offset



    def acquire(self, blocking=True, timeout=None, step=0.25, force=False):
        '''
        Attempts to acquire the lock, will block and retry
        indefinitly by default. Can be configured not to block,
        or to have a timeout. You can also force the aquisition
        if you have a really good reason to do so.

        :param blocking: If true (default), will wait until lock is acquired.
        :type key: bool
        :param timeout: blocking acquire will fail after timeout in seconds if the lock hasn't been acquired yet.
        :type timeout: int
        :param step: delay between acquire attempts
        :type step: float or int
        :param force: CAUTION: will forcibly take ownership of the lock
        :type force: bool


        '''
        if self.timeparanoid is True and self._sanetime is None:
            timeok, offset = self._verifytime()
            if timeok:
                self._sanetime = True
            else:
                raise Exception("Time offset compared to mongodb is too high {}".format(round(offset, 2)))
        if blocking is False and timeout:
            raise ValueError("Blocking can't be false with a timeout set")
        count = 0
        start = datetime.utcnow()
        while self._acquireretry(blocking, start, timeout, count):
            count += 1
            try:
                # force cleanup
                self._db.remove({'ts_expire': {'$lt': datetime.utcnow(),},})
                self.ts_created = datetime.utcnow()
                self.ts_expire = self.ts_created + timedelta(seconds=int(self._ttl))
                payload = {'_id': self.key,
                           'locked': True,
                           'host': self.host,
                           'uuid': self.uuid,
                           'ts_created': self.ts_created,
                           'ts_expire': self.ts_expire}
                if force:
                    res = self._db.find_one_and_replace({'_id': self.key,}, payload, new=True)
                else:
                    res = self._db.insert(payload)
                return res
            except DuplicateKeyError:
                existing = self._db.find_one({'_id': self.key})
                countdown = (datetime.utcnow() - existing['ts_expire']).total_seconds
                if not blocking:
                    raise LockExists('Lock {} exists on host {}, expries in {} seconds'.format(self.key,
                                                                                               existing['host'],
                                                                                               countdown))
                else:
                    sleep(step)
        raise AcquireTimeout("Timeout reached, lock not acquired")


    def locked(self):
        '''
        Returns current status of the lock, but does not indicate if
        the current instance has ownership or not. (for that, use 'self.owned()')
        This is a 'look before you leap' option. For example, it can be used
        to ensure that some process is owns the lock and is doing the associated work.
        Obviously this method does not guaruntee that the current instance will be
        successful in obtaining the lock on a subseqent acquire.

        :return: Lock status
        :rtype: bool
        '''
        locked = False
        res = self._db.find_one({'_id': self.key})
        if res:
            if res['ts_expire'] < datetime.utcnow():
                locked = False
            else:
                locked = res['locked']
        return locked

    def owned(self):
        '''
        Determines if self is the owner of the lock object.
        This verifies the instance uuid matches the
        uuid of the lock record in the db.

        :return: Owner status
        :rtype: bool
        '''
        return bool(self._db.find_one({'_id': self.key,
                                       'uuid': self.uuid,
                                       'locked': True,
                                       'ts_expire': {'$gt': datetime.utcnow(),},}))


    def release(self, force=False):
        '''
        releases lock if owned by the current instance.

        :param force: CAUTION: Forces the release to happen,
        even if the local instance isn't the lock owner.
        :type force: bool
        '''
        if not force:
            query = {'_id': self.key,}
        else:
            query = {'_id': self.key,
                     'uuid': self.uuid}
        self._db.find_and_modify(query, {'$set': {'locked': False}})


    def touch(self):
        '''
        Renews lock expiration timestamp
        :return: new exipiration timestamp
        :rtype: datetime
        '''
        ts_expire = self.ts_created + timedelta(seconds=int(self._ttl))
        self._db.find_and_modify({'_id': self.key,
                                  'uuid': self.uuid,
                                  'locked': True,},
                                 {'$set': {'ts_expire': ts_expire}})
        self.ts_expire = ts_expire
        return self.ts_expire

