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
def fee_token(project, deployer):
    return project.MockToken.deploy(sender=deployer)

@pytest.fixture
def voting(chain, project, deployer, measure, fee_token):
    return project.InclusionVote.deploy(chain.pending_timestamp - EPOCH_LENGTH, measure, fee_token, sender=deployer)

def test_apply(alice, token, voting):
    assert not voting.has_applied(token)
    assert voting.apply_open()
    voting.apply(token, sender=alice)
    assert voting.has_applied(token)

    # cannot apply again in same epoch
    with ape.reverts():
        voting.apply(token, sender=alice)

def test_apply_initial_fee(deployer, alice, fee_token, token, voting):
    voting.set_application_fees(2 * UNIT, UNIT, sender=deployer)
    fee_token.mint(alice, 2 * UNIT, sender=deployer)

    with ape.reverts():
        voting.apply(token, sender=alice)
    fee_token.approve(voting, 2 * UNIT, sender=alice)
    voting.apply(token, sender=alice)
    assert voting.has_applied(token)
    assert fee_token.balanceOf(voting) == 2 * UNIT

def test_apply_subsequent_fee(chain, deployer, alice, bob, fee_token, token, voting):
    voting.set_application_fees(2 * UNIT, UNIT, sender=deployer)
    fee_token.mint(alice, 2 * UNIT, sender=deployer)
    fee_token.approve(voting, 2 * UNIT, sender=alice)
    voting.apply(token, sender=alice)
    chain.pending_timestamp += EPOCH_LENGTH
    voting.finalize_epoch(sender=alice)
    assert not voting.has_applied(token)

    # apply again next epoch
    fee_token.mint(bob, UNIT, sender=deployer)
    fee_token.approve(voting, UNIT, sender=bob)
    voting.apply(token, sender=bob)
    assert fee_token.balanceOf(voting) == 3 * UNIT

def test_sweep_fee(deployer, alice, bob, fee_token, token, voting):
    voting.set_application_fees(2 * UNIT, UNIT, sender=deployer)
    fee_token.mint(alice, 2 * UNIT, sender=deployer)
    fee_token.approve(voting, 2 * UNIT, sender=alice)
    voting.apply(token, sender=alice)
    voting.set_treasury(bob, sender=deployer)
    assert voting.treasury() == bob.address

    # only treasury can sweep
    with ape.reverts():
        voting.sweep(fee_token, deployer, sender=deployer)
    voting.sweep(fee_token, deployer, sender=bob)
    assert fee_token.balanceOf(deployer) == 2 * UNIT

def test_set_provider_whitelist(deployer, alice, bob, token, voting):
    epoch = voting.epoch()
    voting.apply(token, sender=alice)
    assert voting.rate_providers(token) == ZERO_ADDRESS
    assert voting.num_candidates(epoch) == 0
    assert voting.candidates(epoch, 1) == ZERO_ADDRESS
    assert voting.candidates_map(epoch, token) == 0

    # setting a rate provider of a token that applied will automatically whitelist it
    voting.set_operator(bob, sender=deployer)
    with ape.reverts():
        voting.set_rate_provider(token, RATE_PROVIDER, sender=alice)
    voting.set_rate_provider(token, RATE_PROVIDER, sender=bob)
    assert voting.rate_providers(token) == RATE_PROVIDER
    assert voting.num_candidates(epoch) == 1
    assert voting.candidates(epoch, 1) == token.address
    assert voting.candidates_map(epoch, token) == 1

def test_apply_whitelist(deployer, alice, token, voting):
    epoch = voting.epoch()
    voting.set_rate_provider(token, RATE_PROVIDER, sender=deployer)
    assert voting.rate_providers(token) == RATE_PROVIDER
    assert voting.num_candidates(epoch) == 0
    assert voting.candidates(epoch, 1) == ZERO_ADDRESS
    assert voting.candidates_map(epoch, token) == 0

    # applying for a token with rate provider automatically whitelists it
    voting.apply(token, sender=alice)
    assert voting.num_candidates(epoch) == 1
    assert voting.candidates(epoch, 1) == token.address
    assert voting.candidates_map(epoch, token) == 1

def test_apply_whitelist_multiple(deployer, alice, token, token2, voting):
    epoch = voting.epoch()
    voting.set_rate_provider(token, RATE_PROVIDER, sender=deployer)
    voting.set_rate_provider(token2, RATE_PROVIDER, sender=deployer)
    assert voting.rate_providers(token) == RATE_PROVIDER
    assert voting.rate_providers(token2) == RATE_PROVIDER
    
    voting.apply(token, sender=alice)
    voting.apply(token2, sender=alice)
    assert voting.num_candidates(epoch) == 2
    assert voting.candidates(epoch, 1) == token.address
    assert voting.candidates(epoch, 2) == token2.address
    assert voting.candidates_map(epoch, token) == 1
    assert voting.candidates_map(epoch, token2) == 2

def test_vote(chain, deployer, alice, bob, measure, token, token2, voting):
    epoch = voting.epoch()
    voting.set_rate_provider(token, RATE_PROVIDER, sender=deployer)
    voting.set_rate_provider(token2, RATE_PROVIDER, sender=deployer)
    voting.apply(token, sender=alice)
    voting.apply(token2, sender=alice)
    measure.set_vote_weight(alice, 10 * UNIT, sender=alice)
    
    # cant vote too early
    with ape.reverts():
        voting.vote([4000, 6000], sender=alice)

    chain.pending_timestamp += VOTE_START
    chain.mine()
    assert voting.vote_open()

    # votes need to add up
    with ape.reverts():
        voting.vote([5000, 6000], sender=alice)

    assert voting.votes_user(alice, epoch) == 0
    voting.vote([4000, 6000], sender=alice)
    assert voting.total_votes(epoch) == 10 * UNIT
    assert voting.votes_user(alice, epoch) == 10 * UNIT
    assert voting.votes(epoch, 0) == 4 * UNIT
    assert voting.votes(epoch, 1) == 6 * UNIT
    assert voting.votes(epoch, 2) == 0

    # cant vote multiple times
    with ape.reverts():
        voting.vote([4000, 6000], sender=alice)

    # cant vote on non-existing candidates
    measure.set_vote_weight(bob, 20 * UNIT, sender=alice)
    with ape.reverts():
        voting.vote([0, 0, 0, 10000], sender=bob)

    # votes sum up
    voting.vote([0, 7000, 3000], sender=bob)
    assert voting.total_votes(epoch) == 30 * UNIT
    assert voting.votes_user(bob, epoch) == 20 * UNIT
    assert voting.votes(epoch, 0) == 4 * UNIT
    assert voting.votes(epoch, 1) == 20 * UNIT
    assert voting.votes(epoch, 2) == 6 * UNIT

def test_finalize(chain, deployer, alice, bob, measure, token, token2, voting):
    epoch = voting.epoch()
    voting.set_rate_provider(token, RATE_PROVIDER, sender=deployer)
    voting.set_rate_provider(token2, RATE_PROVIDER2, sender=deployer)
    voting.apply(token, sender=alice)
    voting.apply(token2, sender=alice)
    measure.set_vote_weight(alice, UNIT, sender=alice)
    chain.pending_timestamp += VOTE_START
    voting.vote([1000, 6000, 3000], sender=alice)

    # cant finalize before epoch is over
    voting.finalize_epoch(sender=bob)
    assert voting.latest_finalized_epoch() == epoch - 1

    # finalize
    chain.pending_timestamp += WEEK
    voting.finalize_epoch(sender=bob)
    assert voting.latest_finalized_epoch() == epoch
    assert voting.winners(epoch) == token.address
    assert voting.winner_rate_providers(epoch) == RATE_PROVIDER
    assert voting.rate_providers(token) == APPLICATION_DISABLED

    # winners cant apply anymore
    with ape.reverts():
        voting.apply(token, sender=alice)

def test_blank_winner(chain, deployer, alice, bob, measure, token, token2, voting):
    epoch = voting.epoch()
    voting.set_rate_provider(token, RATE_PROVIDER, sender=deployer)
    voting.apply(token, sender=alice)
    measure.set_vote_weight(alice, UNIT, sender=alice)
    chain.pending_timestamp += VOTE_START
    voting.vote([6000, 4000], sender=alice)
    chain.pending_timestamp += WEEK
    voting.finalize_epoch(sender=bob)
    assert voting.latest_finalized_epoch() == epoch
    assert voting.winners(epoch) == ZERO_ADDRESS
    assert voting.winner_rate_providers(epoch) == ZERO_ADDRESS

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
