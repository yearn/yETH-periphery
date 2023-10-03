import ape
import pytest

TOKEN = '0x1BED97CBC3c24A4fb5C069C6E311a967386131f7'
STAKING = '0x583019fF0f430721aDa9cfb4fac8F06cA104d0B4'
BOOTSTRAP = '0x7cf484D9d16BA26aB3bCdc8EC4a73aC50136d491'
YCHAD = '0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52'
UNIT = 1_000_000_000_000_000_000
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'
WEEK_LENGTH = 7 * 24 * 60 * 60

@pytest.fixture
def token():
    return ape.Contract(TOKEN)

@pytest.fixture
def staking():
    return ape.Contract(STAKING)

@pytest.fixture
def bootstrap():
    return ape.Contract(BOOTSTRAP)

@pytest.fixture
def dstaking(project, deployer, staking):
    return project.DelegatedStaking.deploy(staking, sender=deployer)

@pytest.fixture
def measure(project, deployer, staking, bootstrap, dstaking):
    return project.DelegateMeasure.deploy(staking, bootstrap, dstaking, sender=deployer)

def test_bootstrap_weight(staking, bootstrap, measure):
    weight = measure.vote_weight(YCHAD)
    assert weight > 0
    assert weight == staking.vote_weight(bootstrap) * bootstrap.deposits(YCHAD) // bootstrap.deposited()

def test_delegate_weight(chain, accounts, deployer, token, staking, dstaking, measure):
    management = accounts[token.management()]
    token.set_minter(deployer, sender=management)
    token.mint(deployer, 2 * UNIT, sender=deployer)
    token.approve(staking, 2 * UNIT, sender=deployer)
    staking.mint(UNIT, sender=deployer)
    staking.approve(dstaking, UNIT, sender=deployer)
    dstaking.deposit(UNIT, sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()

    before = measure.vote_weight(YCHAD)
    measure.delegate(deployer, YCHAD, sender=deployer)
    assert measure.vote_weight(YCHAD) == before

    measure.set_delegate_multiplier(5000, sender=deployer)
    after = measure.vote_weight(YCHAD)
    assert after > before
    assert after == before + UNIT // 2

def test_multiple_delegate(deployer, alice, bob, measure):
    measure.delegate(alice, deployer, sender=deployer)
    assert measure.delegator(alice) == deployer
    assert measure.delegated(deployer) == alice

    with ape.reverts():
        measure.delegate(bob, deployer, sender=deployer)

    measure.delegate(alice, bob, sender=deployer)
    assert measure.delegator(alice) == bob
    assert measure.delegated(deployer) == ZERO_ADDRESS
    assert measure.delegated(bob) == alice

def test_remove_delegate(deployer, alice, measure):
    measure.delegate(alice, deployer, sender=deployer)
    measure.delegate(alice, ZERO_ADDRESS, sender=deployer)
    assert measure.delegator(alice) == ZERO_ADDRESS
    assert measure.delegated(deployer) == ZERO_ADDRESS

def test_delegate_previous(chain, accounts, deployer, alice, token, staking, dstaking, measure):
    # delegated voting weight should not be manipulatable, currently fails
    management = accounts[token.management()]
    token.set_minter(deployer, sender=management)
    token.mint(deployer, 4 * UNIT, sender=deployer)
    token.approve(staking, 4 * UNIT, sender=deployer)
    staking.mint(2 * UNIT, sender=deployer)
    staking.approve(dstaking, 2 * UNIT, sender=deployer)
    dstaking.deposit(UNIT, sender=deployer)
    chain.pending_timestamp += 7 * 86400
    chain.mine()

    measure.set_delegate_multiplier(5000, sender=deployer)
    measure.delegate(deployer, alice, sender=deployer)
    weight = measure.vote_weight(alice)
    assert weight > 0

    # depositing in same week should not increase weight
    dstaking.deposit(UNIT, sender=deployer)
    assert measure.vote_weight(alice) == weight
