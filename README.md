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

As a context manager:

```python
with MongoLocker("my-resource", db, ttl=30) as lock:
    # lock is acquired automatically
    pass
# lock is released on exit
```

Non-blocking acquire:

```python
from mongoelector import LockExists

lock = MongoLocker("my-resource", db, ttl=30)
try:
    lock.acquire(blocking=False)
except LockExists:
    print("Lock is already held")
```

Blocking acquire with timeout:

```python
from mongoelector import AcquireTimeout

lock = MongoLocker("my-resource", db, ttl=30)
try:
    lock.acquire(timeout=5)
except AcquireTimeout:
    print("Could not acquire lock within 5 seconds")
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

As a context manager:

```python
from time import sleep

with MongoLeaderElector("my-service", db, ttl=15, on_leader=became_leader) as elector:
    while elector.running:
        sleep(1)
# elector is stopped and leadership released on exit
```

Check cluster state:

```python
print(f"Is leader: {elector.is_leader}")
print(f"Leader exists: {elector.leader_exists}")
print(f"Node status: {elector.node_status}")
print(f"Cluster detail: {elector.cluster_detail}")
```

## API Reference

### MongoLocker

```python
MongoLocker(
    key: str,
    db,                          # pymongo Database instance
    *,
    dbcollection: str = "mongolocker",
    ttl: int | float = 600,
    timeparanoid: bool = True,
    maxoffset: float = 0.5,
)
```

| Parameter | Description |
|-----------|-------------|
| `key` | Lock identifier |
| `db` | pymongo `Database` instance |
| `dbcollection` | MongoDB collection name for lock storage |
| `ttl` | Lock time-to-live in seconds |
| `timeparanoid` | Verify host clock offset against MongoDB before acquiring |
| `maxoffset` | Maximum allowed clock offset in seconds |

**Methods:**

| Method | Description |
|--------|-------------|
| `acquire(blocking=True, timeout=None, step=0.25, force=False)` | Acquire the lock |
| `release(force=False)` | Release the lock |
| `touch()` | Renew the lock TTL, returns new expiration or `None` |
| `locked()` | `True` if the lock is held by anyone |
| `owned()` | `True` if the lock is held by this instance |
| `get_current()` | Return the current lock document or `None` |

**Properties:** `uuid`, `host`, `pid`, `ts_expire`, `status`

**Exceptions:**

| Exception | Raised when |
|-----------|------------|
| `LockExists` | Non-blocking acquire fails because the lock is already held |
| `AcquireTimeout` | Blocking acquire exceeds the timeout |
| `TimeOffsetError` | Host clock offset exceeds `maxoffset` (timeparanoid mode) |

### MongoLeaderElector

```python
MongoLeaderElector(
    key: str,
    db,                          # pymongo Database instance
    *,
    ttl: int = 15,
    on_leader=None,              # callback: became leader
    on_leader_loss=None,         # callback: lost leadership
    on_loop=None,                # callback: after each poll cycle
    app_version=None,            # optional version string for status reporting
    report_status: bool = True,
)
```

| Parameter | Description |
|-----------|-------------|
| `key` | Election group identifier |
| `db` | pymongo `Database` instance |
| `ttl` | Leader lease TTL in seconds |
| `on_leader` | Called (no args) when this instance becomes leader |
| `on_leader_loss` | Called (no args) when this instance loses leadership |
| `on_loop` | Called (no args) after each poll cycle |
| `app_version` | Application version string included in status reports |
| `report_status` | Whether to report node status to MongoDB |

**Methods:**

| Method | Description |
|--------|-------------|
| `start(blocking=False)` | Start the background elector thread |
| `stop()` | Stop the elector thread and release leadership |
| `poll()` | Execute a single poll cycle manually |
| `release()` | Release leadership immediately |

**Properties:** `key`, `db`, `ttl`, `mlock`, `running`, `is_leader`, `leader_exists`, `poll_wait`, `node_status`, `cluster_detail`

## Requirements

- Python >= 3.10
- pymongo >= 4.13, < 5.0

## License

Apache 2.0
