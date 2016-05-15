import uuid
from socket import getfqdn
from datetime import datetime, timedelta
from pymongo.errors import DuplicateKeyError

class LockExists(Exception):
    '''Raise when a lock exists'''
    pass

class MongoLocker(object):
    '''Distributed Lock in MongoDB'''

    def __init__(self, key=None, dbconn=None, ttl=600):
        '''
        Create a lock object


        by default, lock will expire after 300 seconds
        if it has not been renewed
        '''
        self.uuid = uuid.uuid4()
        self.host = getfqdn()
        self.ts_expire = None
        self.ts_created = None
        if key and dbconn:
            self.key = key
            self._db = dbconn.locks
        else:
            raise ValueError("must provide key name and pyongo connection instance")
        if ttl:
            if isinstance(ttl, int):
                self._ttl = ttl
            else:
                raise ValueError("ttl must be int() seconds")


    def aquire(self):
        '''
        attempts to aquire the lock
        '''
        try:
            self.ts_created = datetime.utcnow()
            self.ts_expire = self.ts_created + timedelta(seconds=int(self._ttl))
            res = self._db.insert({
                '_id': self.key,
                'locked': True,
                'host': self.host,
                'uuid': self.uuid,
                'ts_created': self.ts_created,
                'ts_expire': self.ts_expire
            })
            return res
        except DuplicateKeyError:
            existing = self._db.find_one({'_id': self.key})
            countdown = (datetime.utcnow() - existing['ts_expire']).total_seconds
            raise LockExists('Lock {} exists on host {}, expries in {} seconds'.format(self.key,
                                                                                       existing['host'],
                                                                                       countdown))


    def locked(self):
        '''
        returns status (bool) of lock
        '''
        locked = False
        res = self._db.find_one({'_id': self.key})
        if res:
            if res['ts_expire'] < datetime.utcnow():
                locked = False
            else:
                locked = res['locked']
        return locked

    def release(self):
        '''
        releases lock
        '''
        self._db.find_and_modify({'_id': self.key,
                                  'uuid': self.uuid},
                                 {'$set': {'locked': False}})
