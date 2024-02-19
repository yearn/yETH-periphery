import ape
import pytest

WEEK = 7 * 24 * 60 * 60
VOTE_START = 3 * WEEK
EPOCH_LENGTH = 4 * WEEK
UNIT = 1_000_000_000_000_000_000
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'
RATE_PROVIDER = '0x1234123412341234123412341234123412341234'
RATE_PROVIDER2 = '0x5678567856785678567856785678567856785678'
APPLICATION_DISABLED = '0x0000000000000000000000000000000000000001'

@pytest.fixture
def measure(project, deployer):
    return project.MockMeasure.deploy(sender=deployer)

@pytest.fixture
def token(project, deployer):
    return project.MockToken.deploy(sender=deployer)

@pytest.fixture
def token2(project, deployer):
    return project.MockToken.deploy(sender=deployer)

@pytest.fixture
def incentive_token(project, deployer):
    return project.MockToken.deploy(sender=deployer)

@pytest.fixture
def voting(chain, project, deployer, measure):
    voting = project.InclusionVote.deploy(chain.pending_timestamp - EPOCH_LENGTH, measure, ZERO_ADDRESS, sender=deployer)
    voting.set_enable_epoch(1, sender=deployer)
    return voting

@pytest.fixture
def incentives(project, deployer, voting):
    return project.InclusionIncentives.deploy(voting, sender=deployer)

def test_deposit(alice, token, incentive_token, incentives):
    epoch = incentives.epoch()
    incentive_token.mint(alice, UNIT, sender=alice)
    incentive_token.approve(incentives, UNIT, sender=alice)
    assert incentives.incentives(epoch, token, incentive_token) == 0
    assert incentives.incentives_depositor(alice, epoch, token, incentive_token) == 0
    assert incentives.unclaimed(epoch, token) == 0
    incentives.deposit(token, incentive_token, UNIT, sender=alice)
    assert incentives.incentives(epoch, token, incentive_token) == UNIT
    assert incentives.incentives_depositor(alice, epoch, token, incentive_token) == UNIT
    assert incentives.unclaimed(epoch, incentive_token) == UNIT

def test_deposit_deadline(chain, deployer, alice, token, incentive_token, incentives):
    incentive_token.mint(alice, UNIT, sender=alice)
    incentive_token.approve(incentives, UNIT, sender=alice)
    incentives.set_deposit_deadline(VOTE_START, sender=deployer)

    chain.pending_timestamp += VOTE_START
    with ape.reverts():
        incentives.deposit(token, incentive_token, UNIT, sender=alice)

def test_claim(chain, deployer, alice, bob, measure, token, incentive_token, voting, incentives):
    epoch = incentives.epoch()
    incentive_token.mint(alice, 6 * UNIT, sender=alice)
    incentive_token.approve(incentives, 6 * UNIT, sender=alice)
    incentives.deposit(token, incentive_token, 6 * UNIT, sender=alice)
    voting.set_rate_provider(token, RATE_PROVIDER, sender=deployer)
    voting.apply(token, sender=alice)
    measure.set_vote_weight(alice, UNIT, sender=alice)
    measure.set_vote_weight(bob, 2 * UNIT, sender=alice)
    chain.pending_timestamp += VOTE_START
    voting.vote([10000, 0], sender=alice)
    voting.vote([0, 10000], sender=bob)
    chain.pending_timestamp += WEEK
    voting.finalize_epochs(sender=alice)
    assert voting.winners(epoch) == token.address

    # everyone that voted will be eligible for incentives
    assert incentives.claimable(epoch, incentive_token, alice) == 2 * UNIT
    incentives.claim(epoch, incentive_token, alice, sender=bob)
    assert incentives.claimable(epoch, incentive_token, alice) == 0
    assert incentive_token.balanceOf(alice) == 2 * UNIT
    assert incentives.unclaimed(epoch, incentive_token) == 4 * UNIT

    # claiming a second time does nothing
    incentives.claim(epoch, incentive_token, alice, sender=bob)
    assert incentive_token.balanceOf(alice) == 2 * UNIT
    assert incentives.unclaimed(epoch, incentive_token) == 4 * UNIT

    # bob claim
    assert incentives.claimable(epoch, incentive_token, bob) == 4 * UNIT
    incentives.claim(epoch, incentive_token, bob, sender=bob)
    assert incentive_token.balanceOf(bob) == 4 * UNIT

def test_claim_fee(chain, deployer, alice, measure, token, incentive_token, voting, incentives):
    epoch = incentives.epoch()
    incentives.set_fee_rate(1000, sender=deployer)
    incentive_token.mint(alice, 10 * UNIT, sender=alice)
    incentive_token.approve(incentives, 10 * UNIT, sender=alice)
    incentives.deposit(token, incentive_token, 10 * UNIT, sender=alice)
    voting.set_rate_provider(token, RATE_PROVIDER, sender=deployer)
    voting.apply(token, sender=alice)
    measure.set_vote_weight(alice, UNIT, sender=alice)
    chain.pending_timestamp += VOTE_START
    voting.vote([0, 10000], sender=alice)
    chain.pending_timestamp += WEEK
    voting.finalize_epochs(sender=alice)

    assert incentives.claimable(epoch, incentive_token, alice) == 9 * UNIT
    incentives.claim(epoch, incentive_token, sender=alice)
    assert incentives.claimable(epoch, incentive_token, alice) == 0
    assert incentive_token.balanceOf(alice) == 9 * UNIT
    assert incentives.unclaimed(epoch, incentive_token) == UNIT

    # claim fee through a sweep
    chain.pending_timestamp += EPOCH_LENGTH
    chain.mine()
    assert incentives.sweepable(epoch, incentive_token) == UNIT
    incentives.sweep(epoch, incentive_token, sender=deployer)
    assert incentive_token.balanceOf(deployer) == UNIT

def test_refund(chain, deployer, alice, bob, measure, token, incentive_token, voting, incentives):
    epoch = incentives.epoch()
    incentive_token.mint(alice, UNIT, sender=alice)
    incentive_token.approve(incentives, UNIT, sender=alice)
    incentives.deposit(token, incentive_token, UNIT, sender=alice)
    voting.set_rate_provider(token, RATE_PROVIDER, sender=deployer)
    voting.apply(token, sender=alice)
    measure.set_vote_weight(alice, UNIT, sender=alice)
    chain.pending_timestamp += VOTE_START
    voting.vote([10000], sender=alice)
    chain.pending_timestamp += WEEK
    voting.finalize_epochs(sender=alice)
    assert voting.winners(epoch) == ZERO_ADDRESS

    # incentives of loser cant be claimed
    assert incentives.claimable(epoch, incentive_token, alice) == 0
    incentives.claim(epoch, incentive_token, alice, sender=bob)
    assert incentive_token.balanceOf(alice) == 0

    assert incentives.refundable(epoch, token, incentive_token, alice) == UNIT
    assert incentives.unclaimed(epoch, incentive_token) == UNIT
    incentives.refund(epoch, token, incentive_token, alice, sender=bob)
    assert incentives.refundable(epoch, token, incentive_token, alice) == 0
    assert incentives.unclaimed(epoch, incentive_token) == 0
    assert incentive_token.balanceOf(alice) == UNIT

def test_sweep(chain, deployer, alice, bob, charlie, measure, token, incentive_token, voting, incentives):
    epoch = incentives.epoch()
    incentive_token.mint(alice, 6 * UNIT, sender=alice)
    incentive_token.approve(incentives, 6 * UNIT, sender=alice)
    incentives.deposit(token, incentive_token, 6 * UNIT, sender=alice)
    voting.set_rate_provider(token, RATE_PROVIDER, sender=deployer)
    voting.apply(token, sender=alice)
    measure.set_vote_weight(alice, UNIT, sender=alice)
    measure.set_vote_weight(bob, 2 * UNIT, sender=alice)
    chain.pending_timestamp += VOTE_START
    voting.vote([10000, 0], sender=alice)
    voting.vote([0, 10000], sender=bob)
    chain.pending_timestamp += WEEK
    voting.finalize_epochs(sender=alice)
    incentives.claim(epoch, incentive_token, alice, sender=bob)

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