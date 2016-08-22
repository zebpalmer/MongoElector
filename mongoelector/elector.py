# -*- coding: utf-8 -*-
import threading
from time import sleep
import logging

from mongoelector.locker import MongoLocker, LockExists, AcquireTimeout


class MongoElector(object):
    """
    This object will do lots of awesome distributed master
    election coolness
    """

    def __init__(self, key, dbconn, dbname='mongoelector',
                 ttl=15, onmaster=None, onmasterloss=None, onloop=None):
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
        self._shutdown = False
        self._wasmaster = False
        self.elector_thread = None
        self.key = key
        self.dbconn = dbconn
        self.dbname = dbname
        self.ttl = ttl
        self.callback_onmaster = onmaster
        self.callback_onmasterloss = onmasterloss
        self.callback_onloop = onloop
        self.mlock = MongoLocker(self.key, self.dbconn, dbname=self.dbname,
                                 dbcollection='electorlocks', ttl=self.ttl, timeparanoid=True)

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
            if self.callback_onloop:
                self.callback_onloop()

    def release(self):
        """
        Releases master lock if owned and calls onmasterloss if provided.
        """
        with self._poll_lock:
            self.mlock.release()
            if self._wasmaster and self.callback_onmaster:
                self.callback_onmasterloss()


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
                sleep(2)
