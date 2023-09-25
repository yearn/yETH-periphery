import ape
import pytest

WEEK = 7 * 24 * 60 * 60
VOTE_START = 3 * WEEK
UNIT = 1_000_000_000_000_000_000

STATE_ABSENT    = 0
STATE_PROPOSED  = 1
STATE_PASSED    = 2
STATE_REJECTED  = 3
STATE_RETRACTED = 4
STATE_CANCELLED = 5
STATE_ENACTED   = 6

@pytest.fixture
def measure(project, deployer):
    return project.MockMeasure.deploy(sender=deployer)

@pytest.fixture
def proxy(project, deployer):
    return project.OwnershipProxy.deploy(sender=deployer)

@pytest.fixture
def executor(project, deployer, proxy):
    executor = project.Executor.deploy(proxy, sender=deployer)
    data = proxy.set_management.encode_input(executor)
    proxy.execute(proxy, data, sender=deployer)
    executor.set_governor(deployer, False, sender=deployer)
    return executor

@pytest.fixture
def token(project, deployer):
    return project.MockToken.deploy(sender=deployer)

@pytest.fixture
def governor(chain, project, deployer, measure, executor):
    governor = project.GenericGovernor.deploy(chain.pending_timestamp, measure, executor, sender=deployer)
    executor.set_governor(governor, True, sender=deployer)
    return governor

@pytest.fixture
def script(alice, proxy, executor, token):
    mint = token.mint.encode_input(proxy, UNIT)
    transfer = token.transfer.encode_input(alice, UNIT)
    return executor.script(token, mint) + executor.script(token, transfer)

def test_propose(alice, governor, script):
    assert governor.propose_open()
    assert governor.proposal_state(0) == STATE_ABSENT
    idx = governor.propose(script, sender=alice).return_value
    assert governor.num_proposals() == 1
    assert governor.proposal_state(idx) == STATE_PROPOSED
    assert governor.proposal(idx)['author'] == alice.address

def test_propose_min_weight(deployer, alice, measure, governor, script):
    governor.set_propose_min_weight(UNIT, sender=deployer)
    with ape.reverts():
        governor.propose(script, sender=alice)

    measure.set_vote_weight(alice, 2 * UNIT, sender=alice)
    idx = governor.propose(script, sender=alice).return_value
    assert governor.num_proposals() == 1
    assert governor.proposal_state(idx) == STATE_PROPOSED
    assert governor.proposal(idx)['author'] == alice.address

def test_propose_closed(chain, deployer, governor, script):
    chain.pending_timestamp += VOTE_START
    chain.mine()
    assert not governor.propose_open()
    with ape.reverts():
        governor.propose(script, sender=deployer)

def test_retract_proposal(alice, bob, governor, script):
    idx = governor.propose(script, sender=alice).return_value
    with ape.reverts():
        governor.retract(idx, sender=bob)
    governor.retract(idx, sender=alice)
    assert governor.proposal_state(idx) == STATE_RETRACTED

def test_cancel_proposal(deployer, alice, governor, script):
    idx = governor.propose(script, sender=alice).return_value
    with ape.reverts():
        governor.cancel(idx, sender=alice)
    governor.cancel(idx, sender=deployer)
    assert governor.proposal_state(idx) == STATE_CANCELLED

def test_vote_yea(chain, alice, bob, measure, governor, script):
    assert governor.propose_open()
    assert not governor.vote_open()
    idx = governor.propose(script, sender=alice).return_value
    chain.pending_timestamp += VOTE_START
    chain.mine()
    assert governor.vote_open()

    # no voting power
    with ape.reverts():
        governor.vote_yea(idx, sender=alice)
    
    measure.set_vote_weight(alice, UNIT, sender=alice)
    assert not governor.voted(alice, idx)
    governor.vote_yea(idx, sender=alice)
    assert governor.voted(alice, idx)
    assert governor.proposal(idx).yea == UNIT

    # no double votes
    with ape.reverts():
        governor.vote_yea(idx, sender=alice)

    # votes are added
    measure.set_vote_weight(bob, 2 * UNIT, sender=alice)
    governor.vote_yea(idx, sender=bob)
    assert governor.proposal(idx).yea == 3 * UNIT

def test_vote_nay(chain, alice, bob, measure, governor, script):
    assert governor.propose_open()
    assert not governor.vote_open()
    idx = governor.propose(script, sender=alice).return_value
    chain.pending_timestamp += VOTE_START
    chain.mine()
    assert governor.vote_open()

    # no voting power
    with ape.reverts():
        governor.vote_nay(idx, sender=alice)
    
    measure.set_vote_weight(alice, UNIT, sender=alice)
    assert not governor.voted(alice, idx)
    governor.vote_nay(idx, sender=alice)
    assert governor.voted(alice, idx)
    assert governor.proposal(idx).nay == UNIT

    # no double votes
    with ape.reverts():
        governor.vote_nay(idx, sender=alice)

    # votes are added
    measure.set_vote_weight(bob, 2 * UNIT, sender=alice)
    governor.vote_nay(idx, sender=bob)
    assert governor.proposal(idx).nay == 3 * UNIT

def test_vote(chain, alice, bob, measure, governor, script):
    assert governor.propose_open()
    assert not governor.vote_open()

    idx = governor.propose(script, sender=alice).return_value
    chain.pending_timestamp += VOTE_START
    chain.mine()
    assert governor.vote_open()

    # no voting power
    with ape.reverts():
        governor.vote(idx, 4000, 6000, sender=alice)
    
    measure.set_vote_weight(alice, 10 * UNIT, sender=alice)

    # votes dont add up
    with ape.reverts():
        governor.vote(idx, 6000, 6000, sender=alice)

    assert not governor.voted(alice, idx)
    governor.vote(idx, 4000, 6000, sender=alice)
    assert governor.voted(alice, idx)
    assert governor.proposal(idx).yea == 4 * UNIT
    assert governor.proposal(idx).nay == 6 * UNIT

    # no double votes
    with ape.reverts():
        governor.vote(idx, 6000, 4000, sender=alice)

    # votes are added
    measure.set_vote_weight(bob, 20 * UNIT, sender=alice)
    governor.vote(idx, 5000, 5000, sender=bob)
    assert governor.proposal(idx).yea == 14 * UNIT
    assert governor.proposal(idx).nay == 16 * UNIT

def test_vote_retracted(chain, alice, measure, governor, script):
    assert governor.propose_open()
    assert not governor.vote_open()

    idx = governor.propose(script, sender=alice).return_value
    chain.pending_timestamp += VOTE_START
    measure.set_vote_weight(alice, UNIT, sender=alice)
    governor.retract(idx, sender=alice)
    with ape.reverts():
        governor.vote_yea(idx, sender=alice)

def test_vote_cancelled(chain, deployer, alice, measure, governor, script):
    assert governor.propose_open()
    assert not governor.vote_open()

    idx = governor.propose(script, sender=alice).return_value
    chain.pending_timestamp += VOTE_START
    measure.set_vote_weight(alice, UNIT, sender=alice)
    governor.cancel(idx, sender=deployer)
    with ape.reverts():
        governor.vote_yea(idx, sender=alice)

def test_vote_closed_no_votes(chain, alice, governor, script):
    idx = governor.propose(script, sender=alice).return_value
    chain.pending_timestamp += 4 * WEEK
    chain.mine()
    assert governor.proposal_state(idx) == STATE_REJECTED

def test_vote_closed_yea(chain, alice, bob, measure, governor, script):
    idx = governor.propose(script, sender=alice).return_value
    chain.pending_timestamp += VOTE_START
    chain.mine()
    measure.set_vote_weight(alice, 2 * UNIT, sender=alice)
    governor.vote_yea(idx, sender=alice)
    measure.set_vote_weight(bob, UNIT, sender=alice)
    governor.vote_nay(idx, sender=bob)

    chain.pending_timestamp += WEEK
    chain.mine()
    assert governor.proposal_state(idx) == STATE_PASSED

    # not executed in same epoch
    chain.pending_timestamp += 4 * WEEK
    chain.mine()
    assert governor.proposal_state(idx) == STATE_REJECTED

def test_vote_closed_nay(chain, alice, bob, measure, governor, script):
    idx = governor.propose(script, sender=alice).return_value
    chain.pending_timestamp += VOTE_START
    chain.mine()
    measure.set_vote_weight(alice, 2 * UNIT, sender=alice)
    governor.vote_nay(idx, sender=alice)
    measure.set_vote_weight(bob, UNIT, sender=alice)
    governor.vote_yea(idx, sender=bob)

    chain.pending_timestamp += WEEK
    chain.mine()
    assert governor.proposal_state(idx) == STATE_REJECTED

def test_vote_closed_supermajority_yea(chain, deployer, alice, measure, governor, script):
    governor.set_majority(6666, sender=deployer)
    idx = governor.propose(script, sender=alice).return_value
    chain.pending_timestamp += VOTE_START
    chain.mine()
    measure.set_vote_weight(alice, UNIT, sender=alice)
    governor.vote(idx, 7000, 3000, sender=alice)

    chain.pending_timestamp += WEEK
    chain.mine()
    assert governor.proposal_state(idx) == STATE_PASSED

def test_vote_closed_supermajority_nay(chain, deployer, alice, measure, governor, script):
    governor.set_majority(6666, sender=deployer)
    idx = governor.propose(script, sender=alice).return_value
    chain.pending_timestamp += VOTE_START
    chain.mine()
    measure.set_vote_weight(alice, UNIT, sender=alice)
    governor.vote(idx, 6000, 4000, sender=alice)

    chain.pending_timestamp += WEEK
    chain.mine()
    assert governor.proposal_state(idx) == STATE_REJECTED

def test_execute(chain, alice, bob, measure, token, governor, script):
    idx = governor.propose(script, sender=alice).return_value
    chain.pending_timestamp += VOTE_START
    measure.set_vote_weight(alice, UNIT, sender=alice)
    governor.vote_yea(idx, sender=alice)

    # cannot retract after vote closed
    chain.pending_timestamp += WEEK
    with ape.reverts():
        governor.retract(idx, sender=alice)

    # execute
    assert token.balanceOf(alice) == 0
    governor.execute(idx, script, sender=bob)
    assert token.balanceOf(alice) == UNIT
    assert governor.proposal_state(idx) == STATE_ENACTED

    # can only execute once
    with ape.reverts():
        governor.execute(idx, script, sender=bob)

def test_execute_different(chain, alice, bob, measure, proxy, executor, token, governor, script):
    idx = governor.propose(script, sender=alice).return_value
    chain.pending_timestamp += VOTE_START
    measure.set_vote_weight(alice, UNIT, sender=alice)
    governor.vote_yea(idx, sender=alice)

    # cant execute different script
    chain.pending_timestamp += WEEK
    mint = token.mint.encode_input(proxy, UNIT)
    transfer = token.transfer.encode_input(bob, UNIT)
    script2 = executor.script(token, mint) + executor.script(token, transfer)
    with ape.reverts():
        governor.execute(idx, script2, sender=bob)
    governor.execute(idx, script, sender=bob)

def test_execute_delay(chain, deployer, alice, bob, measure, token, governor, script):
    governor.set_delay(3600, sender=deployer)
    idx = governor.propose(script, sender=alice).return_value
    chain.pending_timestamp += VOTE_START
    chain.mine()
    measure.set_vote_weight(alice, UNIT, sender=alice)
    governor.vote_yea(idx, sender=alice)

    # cant execute before delay
    chain.pending_timestamp += WEEK
    with ape.reverts():
        governor.execute(idx, script, sender=bob)

    chain.pending_timestamp += 3600
    assert token.balanceOf(alice) == 0
    governor.execute(idx, script, sender=bob)
    assert token.balanceOf(alice) == UNIT
    assert governor.proposal_state(idx) == STATE_ENACTED

def test_execute_retracted(chain, alice, bob, measure, governor, script):
    idx = governor.propose(script, sender=alice).return_value
    chain.pending_timestamp += VOTE_START
    chain.mine()
    measure.set_vote_weight(alice, UNIT, sender=alice)
    governor.vote_yea(idx, sender=alice)
    governor.retract(idx, sender=alice)

    # cant execute
    chain.pending_timestamp += WEEK
    with ape.reverts():
        governor.execute(idx, script, sender=bob)

def test_execute_cancelled(chain, deployer, alice, bob, measure, governor, script):
    idx = governor.propose(script, sender=alice).return_value
    chain.pending_timestamp += VOTE_START
    measure.set_vote_weight(alice, UNIT, sender=alice)
    governor.vote_yea(idx, sender=alice)
    
    # cant execute cancelled proposal
    chain.pending_timestamp += WEEK
    governor.cancel(idx, sender=deployer)
    with ape.reverts():
        governor.execute(idx, script, sender=bob)

def test_management_proxy(chain, deployer, alice, bob, measure, proxy, executor, governor):
    # transfer executor+governor management to proxy
    executor.set_management(proxy, sender=deployer)
    governor.set_management(proxy, sender=deployer)
    assert executor.pending_management() == proxy.address
    assert governor.pending_management() == proxy.address

    accept1 = executor.script(executor, executor.accept_management.encode_input())
    set_governor = executor.script(executor, executor.set_governor.encode_input(alice, True))
    accept2 = executor.script(governor, governor.accept_management.encode_input())
    delay = executor.script(governor, governor.set_delay.encode_input(3600))
    
    idx_accept1 = governor.propose(accept1, sender=alice).return_value
    idx_set_governor = governor.propose(set_governor, sender=alice).return_value
    idx_accept2 = governor.propose(accept2, sender=alice).return_value
    idx_delay = governor.propose(delay, sender=alice).return_value

    chain.pending_timestamp += VOTE_START
    measure.set_vote_weight(alice, UNIT, sender=alice)
    governor.vote_yea(idx_accept1, sender=alice)
    governor.vote_yea(idx_set_governor, sender=alice)
    governor.vote_yea(idx_accept2, sender=alice)
    governor.vote_yea(idx_delay, sender=alice)

    # cannot add governor before accepting executor management
    chain.pending_timestamp += WEEK
    with ape.reverts():
        governor.execute(idx_set_governor, set_governor, sender=bob)

    # execute in correct order
    assert executor.management() == deployer.address
    governor.execute(idx_accept1, accept1, sender=bob)
    assert executor.management() == proxy.address
    assert not executor.governors(alice)
    governor.execute(idx_set_governor, set_governor, sender=bob)
    assert executor.governors(alice)

    # cannot set delay before accepting governor management
    chain.pending_timestamp += WEEK
    with ape.reverts():
        governor.execute(idx_delay, delay, sender=bob)

    # execute in correct order
    assert governor.management() == deployer.address
    governor.execute(idx_accept2, accept2, sender=bob)
    assert governor.management() == proxy.address
    assert governor.delay() == 0
    governor.execute(idx_delay, delay, sender=bob)
    assert governor.delay() == 3600