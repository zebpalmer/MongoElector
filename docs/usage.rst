=====
Usage
=====

To use MongoElector in a project::

    import mongoelector


Mongo Elector
=============

.. code-block:: python
   # Instansiate MongoElector object
   self.elector = MongoElector('CleverName', dbconn, ttl=15, dbname='coolproj',
    onmaster=self.onmaster, onmasterloss=self.onmasterloss, onloop=None)

   # start mongoelector
   self.elector.start()


   # log if master
   logging.debug('Master status: {}'.format(self.elector.ismaster))


   # example callbacks

   def onmasterloss(self):
       self.sched.shutdown() # shutdown APScheduler

   def onmaster(self):
       self.sched.start() # start APScheduler


   # shutdown mongoelector, release master lock
   self.elector.stop()

