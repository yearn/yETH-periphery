import ape
import pytest

UNIT = 1_000_000_000_000_000_000
WEEK_LENGTH = 7 * 24 * 60 * 60

@pytest.fixture
def staking(project, deployer):
    return project.MockToken.deploy(sender=deployer)

@pytest.fixture
def dstaking(project, deployer, staking):
    return project.DelegatedStaking.deploy(staking, sender=deployer)

def test_deposit(chain, alice, bob, staking, dstaking):
    assert staking.balanceOf(dstaking) == 0
    assert dstaking.totalSupply() == 0
    assert dstaking.totalAssets() == 0
    assert dstaking.balanceOf(bob) == 0
    assert dstaking.maxWithdraw(bob) == 0
    assert dstaking.maxRedeem(bob) == 0
    assert dstaking.total_vote_weight() == 0
    assert dstaking.vote_weight(bob) == 0
    staking.mint(alice, UNIT, sender=alice)
    staking.approve(dstaking, UNIT, sender=alice)
    dstaking.deposit(UNIT, bob, sender=alice)
    assert staking.balanceOf(dstaking) == UNIT
    assert dstaking.totalSupply() == UNIT
    assert dstaking.totalAssets() == UNIT
    assert dstaking.balanceOf(bob) == UNIT
    assert dstaking.maxWithdraw(bob) == UNIT
    assert dstaking.maxRedeem(bob) == UNIT
    assert dstaking.total_vote_weight() == 0
    assert dstaking.vote_weight(bob) == 0

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    assert dstaking.total_vote_weight() == UNIT
    assert dstaking.vote_weight(bob) == UNIT

    # second deposit
    staking.mint(bob, UNIT, sender=bob)
    staking.approve(dstaking, UNIT, sender=bob)
    dstaking.deposit(UNIT, sender=bob)
    assert staking.balanceOf(dstaking) == 2 * UNIT
    assert dstaking.totalSupply() == 2 * UNIT
    assert dstaking.totalAssets() == 2 * UNIT
    assert dstaking.balanceOf(bob) == 2 * UNIT
    assert dstaking.maxWithdraw(bob) == 2 * UNIT
    assert dstaking.maxRedeem(bob) == 2 * UNIT
    assert dstaking.total_vote_weight() == UNIT
    assert dstaking.vote_weight(bob) == UNIT

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    assert dstaking.total_vote_weight() == 2 * UNIT
    assert dstaking.vote_weight(bob) == 2 * UNIT

def test_mint(chain, alice, bob, staking, dstaking):
    assert staking.balanceOf(dstaking) == 0
    assert dstaking.totalSupply() == 0
    assert dstaking.totalAssets() == 0
    assert dstaking.balanceOf(bob) == 0
    assert dstaking.maxWithdraw(bob) == 0
    assert dstaking.maxRedeem(bob) == 0
    assert dstaking.total_vote_weight() == 0
    assert dstaking.vote_weight(bob) == 0
    staking.mint(alice, UNIT, sender=alice)
    staking.approve(dstaking, UNIT, sender=alice)
    dstaking.mint(UNIT, bob, sender=alice)
    assert staking.balanceOf(dstaking) == UNIT
    assert dstaking.totalSupply() == UNIT
    assert dstaking.totalAssets() == UNIT
    assert dstaking.balanceOf(bob) == UNIT
    assert dstaking.maxWithdraw(bob) == UNIT
    assert dstaking.maxRedeem(bob) == UNIT
    assert dstaking.total_vote_weight() == 0
    assert dstaking.vote_weight(bob) == 0

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    assert dstaking.total_vote_weight() == UNIT
    assert dstaking.vote_weight(bob) == UNIT

    # second mint
    staking.mint(bob, UNIT, sender=bob)
    staking.approve(dstaking, UNIT, sender=bob)
    dstaking.mint(UNIT, sender=bob)
    assert staking.balanceOf(dstaking) == 2 * UNIT
    assert dstaking.totalSupply() == 2 * UNIT
    assert dstaking.totalAssets() == 2 * UNIT
    assert dstaking.balanceOf(bob) == 2 * UNIT
    assert dstaking.maxWithdraw(bob) == 2 * UNIT
    assert dstaking.maxRedeem(bob) == 2 * UNIT
    assert dstaking.total_vote_weight() == UNIT
    assert dstaking.vote_weight(bob) == UNIT

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    assert dstaking.total_vote_weight() == 2 * UNIT
    assert dstaking.vote_weight(bob) == 2 * UNIT

def test_transfer(chain, alice, bob, staking, dstaking):
    staking.mint(alice, 3 * UNIT, sender=alice)
    staking.approve(dstaking, 3 * UNIT, sender=alice)
    dstaking.deposit(3 * UNIT, bob, sender=alice)

    with ape.reverts():
        dstaking.transfer(alice, 4 * UNIT, sender=bob)

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    dstaking.transfer(alice, 2 * UNIT, sender=bob)
    assert dstaking.balanceOf(alice) == 2 * UNIT
    assert dstaking.balanceOf(bob) == UNIT
    assert dstaking.total_vote_weight() == 3 * UNIT
    assert dstaking.vote_weight(alice) == 0
    assert dstaking.vote_weight(bob) == 3 * UNIT
    
    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    assert dstaking.total_vote_weight() == 3 * UNIT
    assert dstaking.vote_weight(alice) == 2 * UNIT
    assert dstaking.vote_weight(bob) == UNIT

def test_transfer_from(chain, alice, bob, charlie, staking, dstaking):
    staking.mint(alice, 3 * UNIT, sender=alice)
    staking.approve(dstaking, 3 * UNIT, sender=alice)
    dstaking.deposit(3 * UNIT, bob, sender=alice)

    with ape.reverts():
        dstaking.transferFrom(bob, charlie, 2 * UNIT, sender=alice)

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    dstaking.approve(alice, 2 * UNIT, sender=bob)
    assert dstaking.allowance(bob, alice) == 2 * UNIT
    dstaking.transferFrom(bob, charlie, 2 * UNIT, sender=alice)
    assert dstaking.balanceOf(charlie) == 2 * UNIT
    assert dstaking.balanceOf(bob) == UNIT
    assert dstaking.total_vote_weight() == 3 * UNIT
    assert dstaking.vote_weight(charlie) == 0
    assert dstaking.vote_weight(bob) == 3 * UNIT

    with ape.reverts():
        dstaking.transferFrom(bob, charlie, UNIT, sender=alice)
    
    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    assert dstaking.total_vote_weight() == 3 * UNIT
    assert dstaking.vote_weight(charlie) == 2 * UNIT
    assert dstaking.vote_weight(bob) == UNIT

def test_withdraw(chain, alice, bob, staking, dstaking):
    staking.mint(alice, 3 * UNIT, sender=alice)
    staking.approve(dstaking, 3 * UNIT, sender=alice)
    dstaking.deposit(3 * UNIT, bob, sender=alice)

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    dstaking.withdraw(2 * UNIT, alice, sender=bob)
    assert staking.balanceOf(dstaking) == UNIT
    assert staking.balanceOf(alice) == 2 * UNIT
    assert dstaking.totalSupply() == UNIT
    assert dstaking.totalAssets() == UNIT
    assert dstaking.balanceOf(bob) == UNIT
    assert dstaking.maxWithdraw(bob) == UNIT
    assert dstaking.maxRedeem(bob) == UNIT
    assert dstaking.total_vote_weight() == 3 * UNIT
    assert dstaking.vote_weight(bob) == 3 * UNIT

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    assert dstaking.total_vote_weight() == UNIT
    assert dstaking.vote_weight(bob) == UNIT

    with ape.reverts():
        dstaking.withdraw(2 * UNIT, sender=bob)

    # second withdraw
    dstaking.withdraw(UNIT, sender=bob)
    assert staking.balanceOf(dstaking) == 0
    assert staking.balanceOf(bob) == UNIT
    assert dstaking.totalSupply() == 0
    assert dstaking.totalAssets() == 0
    assert dstaking.balanceOf(bob) == 0
    assert dstaking.maxWithdraw(bob) == 0
    assert dstaking.maxRedeem(bob) == 0
    assert dstaking.total_vote_weight() == UNIT
    assert dstaking.vote_weight(bob) == UNIT

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    assert dstaking.total_vote_weight() == 0
    assert dstaking.vote_weight(bob) == 0

def test_withdraw_from(chain, alice, bob, charlie, staking, dstaking):
    staking.mint(alice, 3 * UNIT, sender=alice)
    staking.approve(dstaking, 3 * UNIT, sender=alice)
    dstaking.deposit(3 * UNIT, bob, sender=alice)

    with ape.reverts():
        dstaking.withdraw(2 * UNIT, charlie, bob, sender=alice)

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    dstaking.approve(alice, 2 * UNIT, sender=bob)
    dstaking.withdraw(2 * UNIT, charlie, bob, sender=alice)
    assert staking.balanceOf(dstaking) == UNIT
    assert staking.balanceOf(charlie) == 2 * UNIT
    assert dstaking.totalSupply() == UNIT
    assert dstaking.totalAssets() == UNIT
    assert dstaking.balanceOf(bob) == UNIT
    assert dstaking.maxWithdraw(bob) == UNIT
    assert dstaking.maxRedeem(bob) == UNIT
    assert dstaking.total_vote_weight() == 3 * UNIT
    assert dstaking.vote_weight(bob) == 3 * UNIT

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    assert dstaking.total_vote_weight() == UNIT
    assert dstaking.vote_weight(bob) == UNIT

    with ape.reverts():
        dstaking.withdraw(UNIT, charlie, bob, sender=alice)

def test_redeem(chain, alice, bob, staking, dstaking):
    staking.mint(alice, 3 * UNIT, sender=alice)
    staking.approve(dstaking, 3 * UNIT, sender=alice)
    dstaking.deposit(3 * UNIT, bob, sender=alice)

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    dstaking.redeem(2 * UNIT, alice, sender=bob)
    assert staking.balanceOf(dstaking) == UNIT
    assert staking.balanceOf(alice) == 2 * UNIT
    assert dstaking.totalSupply() == UNIT
    assert dstaking.totalAssets() == UNIT
    assert dstaking.balanceOf(bob) == UNIT
    assert dstaking.maxWithdraw(bob) == UNIT
    assert dstaking.maxRedeem(bob) == UNIT
    assert dstaking.total_vote_weight() == 3 * UNIT
    assert dstaking.vote_weight(bob) == 3 * UNIT

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    assert dstaking.total_vote_weight() == UNIT
    assert dstaking.vote_weight(bob) == UNIT

    with ape.reverts():
        dstaking.redeem(2 * UNIT, sender=bob)    

    # second redeem
    dstaking.redeem(UNIT, sender=bob)
    assert staking.balanceOf(dstaking) == 0
    assert staking.balanceOf(bob) == UNIT
    assert dstaking.totalSupply() == 0
    assert dstaking.totalAssets() == 0
    assert dstaking.balanceOf(bob) == 0
    assert dstaking.maxWithdraw(bob) == 0
    assert dstaking.maxRedeem(bob) == 0
    assert dstaking.total_vote_weight() == UNIT
    assert dstaking.vote_weight(bob) == UNIT

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    assert dstaking.total_vote_weight() == 0
    assert dstaking.vote_weight(bob) == 0

def test_redeem_from(chain, alice, bob, charlie, staking, dstaking):
    staking.mint(alice, 3 * UNIT, sender=alice)
    staking.approve(dstaking, 3 * UNIT, sender=alice)
    dstaking.deposit(3 * UNIT, bob, sender=alice)

    with ape.reverts():
        dstaking.redeem(2 * UNIT, charlie, bob, sender=alice)

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    dstaking.approve(alice, 2 * UNIT, sender=bob)
    dstaking.redeem(2 * UNIT, charlie, bob, sender=alice)
    assert staking.balanceOf(dstaking) == UNIT
    assert staking.balanceOf(charlie) == 2 * UNIT
    assert dstaking.totalSupply() == UNIT
    assert dstaking.totalAssets() == UNIT
    assert dstaking.balanceOf(bob) == UNIT
    assert dstaking.maxWithdraw(bob) == UNIT
    assert dstaking.maxRedeem(bob) == UNIT
    assert dstaking.total_vote_weight() == 3 * UNIT
    assert dstaking.vote_weight(bob) == 3 * UNIT

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    assert dstaking.total_vote_weight() == UNIT
    assert dstaking.vote_weight(bob) == UNIT

    with ape.reverts():
        dstaking.redeem(UNIT, charlie, bob, sender=alice)
