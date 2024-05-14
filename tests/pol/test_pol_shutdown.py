import ape
from ape import Contract
import pytest

DAY_LENGTH = 24 * 60 * 60
WEEK_LENGTH = 7 * DAY_LENGTH
NATIVE = '0x0000000000000000000000000000000000000000'
ONE = 1_000_000_000_000_000_000
MAX = 2**256 - 1

@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def treasury(accounts):
    return accounts[1]

@pytest.fixture
def alice(accounts):
    return accounts[2]

@pytest.fixture
def bob(accounts):
    return accounts[3]

@pytest.fixture
def token():
    return Contract('0x1BED97CBC3c24A4fb5C069C6E311a967386131f7')

@pytest.fixture
def staking(project, deployer, token):
    return project.MockStaking.deploy(token, sender=deployer)

@pytest.fixture
def pol(project, deployer, token):
    return project.POL.deploy(token, sender=deployer)

@pytest.fixture
def bootstrap():
    return Contract('0x7cf484D9d16BA26aB3bCdc8EC4a73aC50136d491')

@pytest.fixture
def pool(project, deployer):
    return project.MockPool.deploy(sender=deployer)

@pytest.fixture
def shutdown(project, accounts, deployer, alice, treasury, token, pol, bootstrap, pool):
    shutdown = project.Shutdown.deploy(token, bootstrap, pol, sender=deployer)
    shutdown.set_pool(pool, sender=deployer)

    management = accounts[bootstrap.management()]
    bootstrap.allow_repay(treasury, True, sender=management)
    bootstrap.allow_repay(shutdown, True, sender=management)
    pol.approve(NATIVE, shutdown, MAX, sender=deployer)

    management = accounts[token.management()]
    token.set_minter(treasury, sender=management)

    debt = bootstrap.debt()
    token.mint(treasury, ONE, sender=treasury)
    token.approve(bootstrap, ONE, sender=treasury)
    bootstrap.repay(ONE, sender=treasury)
    assert bootstrap.debt() == debt - ONE

    token.mint(alice, ONE, sender=treasury)
    token.approve(shutdown, ONE, sender=alice)
    alice.transfer(pol, ONE)

    return shutdown

def test_not_killed(alice, shutdown):
    with ape.reverts():
        shutdown.redeem(ONE, sender=alice)

def test_not_allowed(accounts, deployer, alice, bootstrap, pool, shutdown):
    management = accounts[bootstrap.management()]
    bootstrap.allow_repay(shutdown, False, sender=management)
    pool.set_killed(True, sender=deployer)

    with ape.reverts():
        shutdown.redeem(ONE, sender=alice)

def test_kill_pool(deployer, alice, token, bootstrap, pool, shutdown):
    # kill pool, activating shutdown module
    pool.set_killed(True, sender=deployer)
    
    # redemption
    pre = alice.balance
    debt = bootstrap.debt()
    tx = shutdown.redeem(ONE, sender=alice)
    assert bootstrap.debt() == debt - ONE
    assert token.balanceOf(alice) == 0
    assert token.balanceOf(shutdown) == 0
    assert token.balanceOf(bootstrap) == 0
    assert alice.balance - pre + tx.total_fees_paid == ONE

def test_kill_pol(deployer, alice, token, bootstrap, pol, shutdown):
    # kill POL, activating shutdown module
    pol.kill(sender=deployer)

    # redemption
    pre = alice.balance
    debt = bootstrap.debt()
    tx = shutdown.redeem(ONE, sender=alice)
    assert bootstrap.debt() == debt - ONE
    assert token.balanceOf(alice) == 0
    assert token.balanceOf(shutdown) == 0
    assert token.balanceOf(bootstrap) == 0
    assert alice.balance - pre + tx.total_fees_paid == ONE
