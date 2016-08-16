# -*- coding: utf-8 -*-
import threading
from time import sleep

from mongoelector.locker import MongoLocker, LockExists


class MongoElector(object):
    """
    This object will do lots of awesome distributed master
    election coolness
    """

    def __init__(self, key, dbconn, dbname='mongoelector',
                 ttl=15, onmaster=None, onmasterloss=None, onloop=None):
        """Initial setup"""
        self.shutdown = False
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
        """Starts mongo elector polling"""
        self.elector_thread = ElectorThread(self)  # give elector thread reference to mongolocker
        self.elector_thread.start()
        if blocking:
            self.elector_thread.join()

    def stop(self):
        """Cleanly stop the elector. Surrender master if owned"""
        self.shutdown = True
        self.elector_thread.join()

    @property
    def running(self):
        """Returns true if the elector logic is running"""
        return self.elector_thread.isAlive()

    @property
    def ismaster(self):
        """Returns True if this instance is master"""
        return self.mlock.owned()

    @property
    def members(self):
        """return list of members"""
        raise NotImplementedError

    @property
    def master_exists(self):
        """Returns a list of all instances that are availbe to become master"""
        return self.mlock.locked()

    def poll(self):
        if self.mlock.owned():
            self._wasmaster = True
            self.mlock.touch()
            if self.callback_onloop:
                self.callback_onloop()
        else:
            if self._wasmaster:
                if self.callback_onmasterloss:
                    self.callback_onmasterloss()
        if not self.master_exists:
            try:
                self.mlock.acquire(blocking=False)
            except LockExists:
                pass
            else:
                if self.mlock.owned():
                    self._wasmaster = True
                    if self.callback_onmaster:
                        self.callback_onmaster()

    def release(self):
        """
        releases master, if local instance owns it,
        allowing other instances to become master
        """
        self.mlock.release()
        sleep(2)  # let other instances fight it out


class ElectorThread(threading.Thread):
    """Calls the election polling logic"""

    def __init__(self, elector):
        super(ElectorThread, self).__init__()
        self.elector = elector

    def run(self):
        """Main loop"""
        while self.elector.shutdown is False:
            self.elector.poll()
            sleep(2)
