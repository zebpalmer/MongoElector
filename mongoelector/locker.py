import uuid
from socket import getfqdn
from time import sleep
from datetime import datetime, timedelta
from pymongo.errors import DuplicateKeyError

class LockExists(Exception):
    '''Raise when a lock exists'''
    pass

class AquireTimeout(Exception):
    '''Raise when can't get lock'''

class MongoLocker(object):
    '''
    Distributed Lock in MongoDB.

    Used by MongoElector, but can be used as a standalone distributed lock.
    '''

    def __init__(self, key=None, dbconn=None, ttl=600):
        '''
        :param key: Name of distributed lock
        :type key: str
        :param dbconn: Pymongo client connection to mongodb collection
        :type dbconn: PyMongo db connection
        :param ttl: Lock will expire (ttl seconds) after aquired unless renewed or released
        :type ttl: int
        '''
        self.uuid = str(uuid.uuid4())
        self.host = getfqdn()
        self.ts_expire = None
        self.ts_created = None
        if key and dbconn:
            self.key = key
            self._db = dbconn
        else:
            raise ValueError("must provide key name and pyongo connection instance")
        if ttl:
            if isinstance(ttl, int):
                self._ttl = ttl
            else:
                raise ValueError("ttl must be int() seconds")

    @staticmethod
    def _aquireretry(blocking, start, timeout, count):
        if blocking is False and count > 0:
            return False
        if blocking is True and count == 0:
            return True
        if timeout:
            if (datetime.utcnow() - start) > timedelta(seconds=timeout):
                return False
            else:
                return True

    def aquire(self, blocking=True, timeout=None, step=0.25, force=False):
        '''
        attempts to aquire the lock

        :param blocking: If true (default), method call
        will wait (timeout) until lock is aquired.
        :type key: bool
        :param timeout: a blocking call will fail after timeout in seconds
        if the lock hasn't been aquired yet.
        :type timeout: int
        :param step: delay between aquire attempts
        :type step: float or int
        :param force: CAUTION: will forcibly take ownership of the lock
        :type force: bool


        '''
        if blocking is False and timeout:
            raise ValueError("Blocking can't be false with a timeout set")
        count = 0
        start = datetime.utcnow()
        while self._aquireretry(blocking, start, timeout, count):
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
                    res = self._db.find_one_and_replace({'_id': key,}, payload, new=True)
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
        raise AquireTimeout("Timeout reached, lock not aquired")


    def locked(self):
        '''
        returns status of lock

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


    def release(self, force=True):
        '''
        releases lock

        :param force: CAUTION: Forces the release to happen,
        even if the local instance isn't the owner.
        :type force: bool
        '''
        self._db.find_and_modify({'_id': self.key,
                                  'uuid': self.uuid},
                                 {'$set': {'locked': False}})

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



