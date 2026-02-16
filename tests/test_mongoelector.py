from random import randint
from time import sleep
from unittest.mock import patch

from mongoelector import MongoLeaderElector


def test_init_elector(db):
    with patch("mongoelector.locker.MongoLocker._verifytime", return_value=True):
        elector = MongoLeaderElector(f"test_init_{randint(0, 10000)}", db)
        assert isinstance(elector, MongoLeaderElector)


def test_leader_election_lifecycle(db):
    with patch("mongoelector.locker.MongoLocker._verifytime", return_value=True):
        elector = MongoLeaderElector(f"test_election_{randint(0, 10000)}", db, ttl=5)
        elector.start()
        for _ in range(10):
            if elector.is_leader:
                break
            sleep(0.5)
        assert elector.is_leader
        assert elector.running
        elector.poll()
        status = elector.node_status
        assert isinstance(status, dict)
        assert status["is_leader"] is True
        assert status["elector_running"] is True
        assert "uuid" in status

        cluster = elector.cluster_detail
        assert isinstance(cluster, dict)
        assert cluster["leader"] is not None

        elector.stop()
        sleep(1)
        assert not elector.is_leader


def test_callbacks(db):
    triggered = {
        "became_leader": False,
        "lost_leader": False,
        "loop_called": False,
    }

    def on_leader():
        triggered["became_leader"] = True

    def on_leader_loss():
        triggered["lost_leader"] = True

    def on_loop():
        triggered["loop_called"] = True

    with patch("mongoelector.locker.MongoLocker._verifytime", return_value=True):
        elector = MongoLeaderElector(
            f"test_callbacks_{randint(0, 10000)}",
            db,
            ttl=4,
            on_leader=on_leader,
            on_leader_loss=on_leader_loss,
            on_loop=on_loop,
        )
        elector.start()
        for _ in range(10):
            if elector.is_leader:
                break
            sleep(0.5)
        assert triggered["became_leader"] is True
        assert triggered["loop_called"] is True
        elector.stop()
        sleep(1)
        assert triggered["lost_leader"] is True


def test_context_manager(db):
    with patch("mongoelector.locker.MongoLocker._verifytime", return_value=True):
        with MongoLeaderElector(f"test_ctx_{randint(0, 10000)}", db, ttl=5) as elector:
            for _ in range(10):
                if elector.is_leader:
                    break
                sleep(0.5)
            assert elector.is_leader
            assert elector.running
        # after exiting context, elector is stopped
        assert not elector.running
        assert not elector.is_leader


def test_repr(db):
    with patch("mongoelector.locker.MongoLocker._verifytime", return_value=True):
        elector = MongoLeaderElector(f"test_repr_{randint(0, 10000)}", db, ttl=5)
        r = repr(elector)
        assert "MongoLeaderElector" in r
        assert "stopped" in r
        assert "follower" in r

        elector.start()
        for _ in range(10):
            if elector.is_leader:
                break
            sleep(0.5)
        r = repr(elector)
        assert "running" in r
        assert "leader" in r
        elector.stop()
