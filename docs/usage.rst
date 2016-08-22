=====
Usage
=====

To use MongoElector in a project::

    import mongoelector


MongoElector
=============

A few random examples of interacting with MongoElector

.. code-block:: python

   # Instantiate MongoElector object
   elector = MongoElector('CleverName', dbconn, ttl=15, dbname='coolproj',
                          onmaster=self.onmaster, onmasterloss=self.onmasterloss)

   # example callbacks

   def onmasterloss():
       logging.info("Master Lost, shutting down task scheduler)
       sched.shutdown() # shutdown APScheduler

   def onmaster():
       logging.info("Elected master, starting task scheduler)
       sched.start() # start APScheduler

   # start mongoelector
   elector.start()

   # shutdown mongoelector, release master lock
   elector.stop()

   # log if master
   logging.debug('master status: {}'.format(elector.ismaster))

   # release the master lock, allowing another instance to take it
   elector.release()

   # log if master exists (on any node)
   logging.debug('Cluster master is running: {}'.format(elector.master_exists))


MongoLocker
===========

.. code-block:: python

    # create Pymongo dbconnection
    dbconn = MongoClient(cfg.dbhost)
    # create lock object with a ttl of 60.
    # If the lock isn't refreshed within ttl seconds, it will auto-expire.
    mlock = MongoLocker(self.key, dbconn, ttl=60, dbname='coolproj',
                        dbcollection='electorlocks')

    # acquire the lock, raise AcquireTimeout after 30 seconds if not acquired.
    mlock.acquire(timeout=30)

    # release lock
    mlock.release()

    # check to see if lock is locked by any instance
    print(mlock.locked())

    # check to see if lock is owned by this instance
    print(mlock.owned())
