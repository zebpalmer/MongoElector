=====
Usage
=====

To use MongoElector in a project::

    import mongoelector


Mongo Elector
=============

.. code-block:: python
   # Instantiate MongoElector object
   self.elector = MongoElector('CleverName', dbconn, ttl=15, dbname='coolproj',
    onmaster=self.onmaster, onmasterloss=self.onmasterloss)

   # example callbacks

   def onmasterloss(self):
       self.sched.shutdown() # shutdown APScheduler

   def onmaster(self):
       self.sched.start() # start APScheduler

   # start mongoelector
   self.elector.start()

   # shutdown mongoelector, release master lock
   self.elector.stop()

   # log if master
   logging.debug('master status: {}'.format(self.elector.ismaster))

