import ape
import pytest

WEEK = 7 * 24 * 60 * 60
VOTE_START = 3 * WEEK
EPOCH_LENGTH = 4 * WEEK
UNIT = 1_000_000_000_000_000_000
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'

@pytest.fixture
def measure(project, deployer):
    return project.MockMeasure.deploy(sender=deployer)

@pytest.fixture
def pool(project, deployer):
    pool = project.MockPool.deploy(sender=deployer)
    pool.set_num_assets(2, sender=deployer)
    return pool

@pytest.fixture
def voting(project, chain, deployer, measure, pool):
    return project.WeightVote.deploy(chain.pending_timestamp, pool, measure, sender=deployer)

def test_vote(chain, alice, bob, measure, voting):
    epoch = voting.epoch()
    chain.pending_timestamp += VOTE_START
    measure.set_vote_weight(alice, 10 * UNIT, sender=alice)

    # votes must add up
    with ape.reverts():
        voting.vote([6000, 5000], sender=alice)

    assert voting.num_assets(epoch) == 0
    assert voting.total_votes(epoch) == 0
    assert not voting.voted(alice, epoch)
    voting.vote([6000, 4000], sender=alice)
    assert voting.num_assets(epoch) == 2
    assert voting.total_votes(epoch) == 10 * UNIT
    assert voting.voted(alice, epoch)
    assert voting.votes(epoch, 0) == 6 * UNIT
    assert voting.votes(epoch, 1) == 4 * UNIT
    assert voting.votes(epoch, 2) == 0

    # cannot vote twice
    with ape.reverts():
        voting.vote([6000, 4000], sender=alice)

    # votes are added
    measure.set_vote_weight(bob, 20 * UNIT, sender=bob)
    voting.vote([0, 3000, 7000], sender=bob)
    assert voting.votes(epoch, 0) == 6 * UNIT
    assert voting.votes(epoch, 1) == 10 * UNIT
    assert voting.votes(epoch, 2) == 14 * UNIT

def test_transfer_management(deployer, alice, bob, voting):
    assert voting.management() == deployer.address
    assert voting.pending_management() == ZERO_ADDRESS
    with ape.reverts():
        voting.set_management(alice, sender=alice)
    
    voting.set_management(alice, sender=deployer)
    assert voting.pending_management() == alice.address

    with ape.reverts():
        voting.accept_management(sender=bob)

    voting.accept_management(sender=alice)
    assert voting.management() == alice.address
    assert voting.pending_management() == ZERO_ADDRESS
