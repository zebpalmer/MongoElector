# MongoElector

Distributed leader election and locking using MongoDB.

## Components

- **MongoLocker** - Standalone distributed lock primitive backed by MongoDB with TTL-based expiration
- **MongoLeaderElector** - Leader election coordinator built on MongoLocker with background polling and callbacks

## Installation

```bash
pip install mongoelector
```

## Quick Start

### Distributed Lock

```python
from pymongo import MongoClient
from mongoelector import MongoLocker

db = MongoClient().my_database
lock = MongoLocker("my-resource", db, ttl=30)

lock.acquire()
try:
    # do work while holding the lock
    pass
finally:
    lock.release()
```

### Leader Election

```python
from pymongo import MongoClient
from mongoelector import MongoLeaderElector

db = MongoClient().my_database

def became_leader():
    print("I am the leader now")

def lost_leadership():
    print("No longer the leader")

elector = MongoLeaderElector(
    "my-service",
    db,
    ttl=15,
    on_leader=became_leader,
    on_leader_loss=lost_leadership,
)
elector.start()
```

## Requirements

- Python >= 3.10
- pymongo >= 4.13

## License

Apache 2.0
