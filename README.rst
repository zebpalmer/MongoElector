===============================
MongoElector
===============================

.. image:: https://badges.gitter.im/zebpalmer/MongoElector.svg
   :alt: Join the chat at https://gitter.im/zebpalmer/MongoElector
   :target: https://gitter.im/zebpalmer/MongoElector?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge

.. image:: https://img.shields.io/pypi/v/mongoelector.svg
        :target: https://pypi.python.org/pypi/mongoelector

.. image:: https://img.shields.io/travis/zebpalmer/MongoElector.svg
        :target: https://travis-ci.org/zebpalmer/MongoElector

.. image:: https://landscape.io/github/zebpalmer/MongoElector/master/landscape.svg?style=flat
        :target: https://landscape.io/github/zebpalmer/MongoElector/master
        :alt: Code Health

.. image:: https://readthedocs.org/projects/mongoelector/badge/?version=latest
        :target: https://readthedocs.org/projects/mongoelector/?badge=latest
        :alt: Documentation Status

.. image:: https://api.codacy.com/project/badge/Grade/9b0eca961d57462aac560bbee862eee7
        :target: https://www.codacy.com/app/zeb/MongoElector?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=zebpalmer/MongoElector&amp;utm_campaign=Badge_Grade




About
======

The MongoElector project provides two pieces of distributed coordination;
Distributed locks via 'MongoLocker' and master elections via 'MongoElector'.
MongoElector makes heavy use of MongoLocker, but the locking functionality
within MongoLocker can be used separately.


* Free software: GPLv3
* Documentation: https://mongoelector.readthedocs.io.

.. NOTE::
   As of 0.3.0 release, the distributed master election functionality is working.
   Additional features and functionality as well as bug fixes and minor API changes
   will be ongoing over the next couple of minor releases.



Features
--------

* Simple API to allow distributed master election
* Distributed locking via MongoDB
* Ensure/Verify a specific instance holds the lock
* TTL


Todo
-----

* Cluster Health and Management within MongoElector
