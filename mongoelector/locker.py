import os
import uuid
import logging
from socket import getfqdn
from threading import Lock
from datetime import datetime, timedelta
from pymongo.errors import DuplicateKeyError 

class LockExists(Exception):
    pass 

class MongoLocker(object):
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
            
    
    def aquire(self, wait=None):
        '''
        attempts to aquire the lock
        '''
        try:
            self.ts_created = datetime.utcnow()
            self.ts_expire = self.ts_created + timedelta(seconds=int(self._ttl))            
            r = self._db.insert({
                '_id': self.key,
                'locked': True,
                'host': self.host,
                'uuid': self.uuid,
                'ts_created': self.ts_created,
                'ts_expire': self.ts_expire
            })
            return r
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
        r = self._db.find_one({'_id': self.key})
        if r:
            if r['ts_expire'] < datetime.utcnow():
                locked = False
            else:   
                locked = r['locked']
        return locked
        
    def release(self):
        '''
        releases lock
        '''
        self._db.find_and_modify({'_id': self.key, 
                                  'uuid': self.uuid},
                                 {'$set': {'locked': False}})
        