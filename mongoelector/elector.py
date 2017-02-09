# -*- coding: utf-8 -*-
import threading
from time import sleep
import logging
from datetime import datetime
from pymongo.errors import OperationFailure


from mongoelector.locker import MongoLocker, LockExists, AcquireTimeout


class MongoElector(object):
    """
    This object will do lots of awesome distributed master
    election coolness
    """

    def __init__(self, key, dbconn, dbname='mongoelector',
                 ttl=15, onmaster=None, onmasterloss=None,
                 onloop=None, report_status=True):
        """
        Create a MongoElector instance

        :param key: Name of the distributed lock that is used for master election.
         should be unique to this type of daemon i.e. any instance for which you want
         to run exactly one master should all share this same name.
        :type key: str
        :param dbconn: Connection to a MongoDB server or cluster
        :type dbconn: PyMongo DB Connection
        :param dbname: Name of the mongodb database to use (will be created if it doesn't exist)
        :type dbname: str
        :param ttl: Time-to-live for the distributed lock. If the master node fails silently, this
         timeout must be hit before another node will take over.
        :type ttl: int
        :param onmaster: Function that will be run every time this instance is elected as the new master
        :type onmaster: Function or Method
        :param onmasterloss: Function that will be run every time when this instance loses it's master status
        :type onmasterloss: Function or Method
        :param onloop: Function that will be run on every loop
        :type onloop: Function or Method
        """
        self._poll_lock = threading.Lock()
        self._ts_poll = None
        self._shutdown = False
        self._wasmaster = False
        self._report_status = report_status
        self.elector_thread = None
        self.key = key
        self.dbconn = dbconn
        self.dbname = dbname
        self._status_db = getattr(getattr(dbconn, dbname), 'elector.status')
        try:
            self._status_db.create_index('timestamp', expireAfterSeconds=int(ttl))
        except OperationFailure:  # Handle TTL Changes
            self._status_db.drop_indexes()
            self._status_db.create_index('timestamp', expireAfterSeconds=int(ttl))
        self._status_db.create_index('key')
        self.ttl = ttl
        self.callback_onmaster = onmaster
        self.callback_onmasterloss = onmasterloss
        self.callback_onloop = onloop
        self.mlock = MongoLocker(self.key, self.dbconn, dbname=self.dbname,
                                 dbcollection='elector.locks', ttl=self.ttl,
                                 timeparanoid=True)

    def start(self, blocking=False):
        """
        Starts mongo elector polling on a background thread then returns.
        If blocking is set to True, this will never return until stop() is

        :param blocking: If False, returns as soon as the elector thread is started.
         If True, will only return after stop() is called i.e. by another thread.
        :type blocking: bool
        """
        self.elector_thread = ElectorThread(self)  # give elector thread reference to mongolocker
        self.elector_thread.start()
        if blocking:
            self.elector_thread.join()

    def stop(self):
        """Cleanly stop the elector. Surrender master if owned"""
        with self._poll_lock:
            self._shutdown = True
            if self.elector_thread:
                self.elector_thread.join()
        self.release()

    @property
    def running(self):
        """Returns true if the elector logic is running"""
        return self.elector_thread.isAlive()

    @property
    def ismaster(self):
        """Returns True if this instance is master"""
        return self.mlock.owned()

    @property
    def master_exists(self):
        """Returns true if an instance (not necessarily this one) has master"""
        return self.mlock.locked()

    def poll(self):
        """
        Main polling logic, will refresh lock if it's owned,
        or tries to obtain the lock if it's available.
        Runs onloop callback after lock maintenance logic

        In general, this should only be called by the elector thread
        """
        with self._poll_lock:
            self._ts_poll = datetime.utcnow()
            if self.mlock.owned():
                self._wasmaster = True
                self.mlock.touch()
            else:
                if self._wasmaster:
                    self._wasmaster = False
                    if self.callback_onmasterloss:
                        self.callback_onmasterloss()

            if not self.master_exists and not self._shutdown:
                try:
                    self.mlock.acquire(blocking=False)
                except (LockExists, AcquireTimeout):
                    pass
                else:
                    if self.mlock.owned():
                        self._wasmaster = True
                        if self.callback_onmaster:
                            self.callback_onmaster()
            if self._report_status:
                self.report_status()
            if self.callback_onloop:
                self.callback_onloop()

    def report_status(self):
        status = self.node_status
        self._status_db.update({'_id': status['_id']}, status, upsert=True)

    @property
    def cluster_detail(self):
        data = [x for x in self._status_db.find({'key': self.key}, {'_id': 0}).sort('timestamp', -1)]
        return {'member_detail': data,
                'master': parse_master(data),
                'timestamp': datetime.utcnow()}

    @property
    def node_status(self):
        """Status info for current object"""
        status = self.mlock.status
        status['_id'] = status['uuid']
        status['ismaster'] = self.ismaster
        status['elector_running'] = self.running
        status['last_poll'] = self._ts_poll
        return status

    def release(self):
        """
        Releases master lock if owned and calls onmasterloss if provided.
        """
        with self._poll_lock:
            self.mlock.release()
            if self._wasmaster and self.callback_onmaster:
                self.callback_onmasterloss()


    @property
    def pollwait(self):
        """An appropriate sleep time to wait before next poll"""
        if self._wasmaster:
            return self.ttl / 2.0
        else:
            return self.ttl


class ElectorThread(threading.Thread):
    """Calls the election polling logic"""

    def __init__(self, elector):
        """Custom Thread object for the Elector"""
        super(ElectorThread, self).__init__()
        self.elector = elector

    def run(self):
        """starts the elector polling logic, should not be called directly"""
        # noinspection PyProtectedMember
        while self.elector._shutdown is False:
            try:
                self.elector.poll()
            except Exception as e:
                logging.warning('Elector Poll Error: {}'.format(e))
            finally:
                sleep(self.elector.pollwait)


def parse_master(data):
    allmasters = [x for x in data if x['ismaster']]  # grab most recent master (prevents race)
    if allmasters:
        master = allmasters[0]
    else:
        master = None
    if master:
        return {'host': master['host'],
                'process_id': master['pid'],
                'uuid': master['uuid']}
    else:
        return None
