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
def incentive_token(project, deployer):
    return project.MockToken.deploy(sender=deployer)

@pytest.fixture
def voting(chain, project, deployer, measure, pool):
    return project.WeightVote.deploy(chain.pending_timestamp - EPOCH_LENGTH, pool, measure, sender=deployer)

@pytest.fixture
def incentives(project, deployer, pool, voting):
    return project.WeightIncentives.deploy(pool, voting, sender=deployer)

def test_deposit(alice, incentive_token, incentives):
    epoch = incentives.epoch()
    incentive_token.mint(alice, UNIT, sender=alice)
    incentive_token.approve(incentives, UNIT, sender=alice)

    with ape.reverts():
        incentives.deposit(3, incentive_token, UNIT, sender=alice)

    assert incentives.incentives(epoch, 2, incentive_token) == 0
    assert incentives.unclaimed(epoch, incentive_token) == 0
    incentives.deposit(2, incentive_token, UNIT, sender=alice)
    assert incentives.incentives(epoch, 2, incentive_token) == UNIT
    assert incentives.unclaimed(epoch, incentive_token) == UNIT

def test_deposit_deadline(chain, deployer, alice, incentive_token, incentives):
    incentive_token.mint(alice, UNIT, sender=alice)
    incentive_token.approve(incentives, UNIT, sender=alice)
    incentives.set_deposit_deadline(VOTE_START, sender=deployer)

    chain.pending_timestamp += VOTE_START
    with ape.reverts():
        incentives.deposit(2, incentive_token, UNIT, sender=alice)

def test_claim(chain, alice, bob, measure, incentive_token, voting, incentives):
    epoch = incentives.epoch()
    incentive_token.mint(alice, 6 * UNIT, sender=alice)
    incentive_token.approve(incentives, 6 * UNIT, sender=alice)
    incentives.deposit(2, incentive_token, 6 * UNIT, sender=alice)
    measure.set_vote_weight(alice, UNIT, sender=alice)
    measure.set_vote_weight(bob, UNIT, sender=alice)
    chain.pending_timestamp += VOTE_START
    voting.vote([5000, 0, 5000], sender=alice)
    voting.vote([0, 0, 10000], sender=bob)
    chain.pending_timestamp += WEEK
    chain.mine()

    # incentives are distributed over those who voted for the choice
    assert incentives.claimable(epoch, 2, incentive_token, alice) == 2 * UNIT
    incentives.claim(epoch, 2, incentive_token, alice, sender=bob)
    assert incentives.claimable(epoch, 2, incentive_token, alice) == 0
    assert incentive_token.balanceOf(alice) == 2 * UNIT
    assert incentives.unclaimed(epoch, incentive_token) == 4 * UNIT

    # claiming a second time does nothing
    incentives.claim(epoch, 2, incentive_token, alice, sender=bob)
    assert incentive_token.balanceOf(alice) == 2 * UNIT
    assert incentives.unclaimed(epoch, incentive_token) == 4 * UNIT

    # bob claim
    assert incentives.claimable(epoch, 2, incentive_token, bob) == 4 * UNIT
    incentives.claim(epoch, 2, incentive_token, bob, sender=bob)
    assert incentive_token.balanceOf(bob) == 4 * UNIT

def test_claim_fee(chain, deployer, alice, measure, incentive_token, voting, incentives):
    epoch = incentives.epoch()
    incentives.set_fee_rate(1000, sender=deployer)
    incentive_token.mint(alice, 10 * UNIT, sender=alice)
    incentive_token.approve(incentives, 10 * UNIT, sender=alice)
    incentives.deposit(2, incentive_token, 10 * UNIT, sender=alice)
    measure.set_vote_weight(alice, UNIT, sender=alice)
    chain.pending_timestamp += VOTE_START
    voting.vote([5000, 0, 5000], sender=alice)
    chain.pending_timestamp += WEEK
    chain.mine()
    assert incentives.claimable(epoch, 2, incentive_token, alice) == 9 * UNIT
    incentives.claim(epoch, 2, incentive_token, sender=alice)
    assert incentives.claimable(epoch, 2, incentive_token, alice) == 0
    assert incentive_token.balanceOf(alice) == 9 * UNIT
    assert incentives.unclaimed(epoch, incentive_token) == UNIT

    # claim fee through a sweep
    chain.pending_timestamp += EPOCH_LENGTH
    chain.mine()
    assert incentives.sweepable(epoch, incentive_token) == UNIT
    incentives.sweep(epoch, incentive_token, sender=deployer)
    assert incentive_token.balanceOf(deployer) == UNIT

def test_sweep(chain, deployer, alice, bob, charlie, measure, incentive_token, voting, incentives):
    epoch = incentives.epoch()
    incentive_token.mint(alice, 6 * UNIT, sender=alice)
    incentive_token.approve(incentives, 6 * UNIT, sender=alice)
    incentives.deposit(2, incentive_token, 6 * UNIT, sender=alice)
    measure.set_vote_weight(alice, UNIT, sender=alice)
    measure.set_vote_weight(bob, UNIT, sender=alice)
    chain.pending_timestamp += VOTE_START
    voting.vote([5000, 0, 5000], sender=alice)
    voting.vote([0, 0, 10000], sender=bob)
    chain.pending_timestamp += WEEK
    incentives.claim(epoch, 2, incentive_token, alice, sender=bob)

    # unclaimed incentives cannot be swept yet
    assert incentives.sweepable(epoch, incentive_token) == 0
    with ape.reverts():
        incentives.sweep(epoch, incentive_token, sender=deployer)

    # sweep unclaimed incentives next epoch
    chain.pending_timestamp += EPOCH_LENGTH
    chain.mine()
    assert incentives.sweepable(epoch, incentive_token) == 4 * UNIT
    incentives.sweep(epoch, incentive_token, charlie, sender=deployer)
    assert incentives.sweepable(epoch, incentive_token) == 0
    assert incentive_token.balanceOf(charlie) == 4 * UNIT

def test_transfer_management(deployer, alice, bob, incentives):
    assert incentives.management() == deployer.address
    assert incentives.pending_management() == ZERO_ADDRESS
    with ape.reverts():
        incentives.set_management(alice, sender=alice)
    
    incentives.set_management(alice, sender=deployer)
    assert incentives.pending_management() == alice.address

    with ape.reverts():
        incentives.accept_management(sender=bob)

    incentives.accept_management(sender=alice)
    assert incentives.management() == alice.address
    assert incentives.pending_management() == ZERO_ADDRESS