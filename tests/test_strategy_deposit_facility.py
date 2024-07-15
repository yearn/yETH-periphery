import ape
from ape import Contract
import pytest

ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'
NATIVE = ZERO_ADDRESS
UNIT = 10**18

@pytest.fixture
def operator(accounts):
    return accounts[4]

@pytest.fixture
def strategy(accounts):
    return accounts[5]

@pytest.fixture
def token():
    return Contract('0x1BED97CBC3c24A4fb5C069C6E311a967386131f7')

@pytest.fixture
def staking():
    return Contract('0x583019fF0f430721aDa9cfb4fac8F06cA104d0B4')

@pytest.fixture
def weth():
    return Contract('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2')

@pytest.fixture
def pol(project, deployer, token):
    return project.POL.deploy(token, sender=deployer)

@pytest.fixture
def facility(project, accounts, deployer, operator, token, pol):
    facility = project.DepositFacility.deploy(token, pol, sender=deployer)
    facility.set_operator(operator, sender=deployer)
    facility.set_capacity(10 * UNIT, sender=deployer)
    management = accounts[token.management()]
    token.set_minter(facility, sender=management)
    return facility

@pytest.fixture
def strategy_facility(project, deployer, strategy, token, staking, weth, facility):
    strategy_facility = project.StrategyDepositFacility.deploy(token, staking, facility, weth, sender=deployer)
    strategy_facility.set_strategy(strategy, sender=deployer)
    facility.set_mint_whitelist(strategy_facility, True, sender=deployer)
    facility.set_burn_whitelist(strategy_facility, True, sender=deployer)
    return strategy_facility

def test_deposit(strategy, token, weth, strategy_facility):
    weth.deposit(value=3 * UNIT, sender=strategy)
    weth.approve(strategy_facility, UNIT, sender=strategy)

    assert weth.balanceOf(strategy) == 3 * UNIT
    assert token.balanceOf(strategy) == 0
    assert strategy_facility.available() == (10 * UNIT, 0)
    assert strategy_facility.deposit(UNIT, False, sender=strategy).return_value == UNIT
    assert weth.balanceOf(strategy) == 2 * UNIT
    assert token.balanceOf(strategy) == UNIT
    assert strategy_facility.available() == (9 * UNIT, UNIT)

def test_deposit_stake(strategy, token, staking, weth, strategy_facility):
    weth.deposit(value=3 * UNIT, sender=strategy)
    weth.approve(strategy_facility, UNIT, sender=strategy)

    assert weth.balanceOf(strategy) == 3 * UNIT
    assert token.balanceOf(strategy) == 0
    actual = strategy_facility.deposit(UNIT, True, sender=strategy).return_value
    shares = staking.convertToShares(UNIT)
    assert actual == shares
    assert weth.balanceOf(strategy) == 2 * UNIT
    assert staking.balanceOf(strategy) == shares

def test_deposit_fee(deployer, strategy, token, weth, strategy_facility):
    strategy_facility.set_fee_rates(100, 0, sender=deployer)
    weth.deposit(value=3 * UNIT, sender=strategy)
    weth.approve(strategy_facility, UNIT, sender=strategy)

    fee = UNIT // 100
    assert weth.balanceOf(strategy) == 3 * UNIT
    assert token.balanceOf(strategy) == 0
    assert strategy_facility.pending_fees() == 0
    assert strategy_facility.balance == 0
    assert strategy_facility.deposit(UNIT, False, sender=strategy).return_value == UNIT - fee
    assert weth.balanceOf(strategy) == 2 * UNIT
    assert token.balanceOf(strategy) == UNIT - fee
    assert strategy_facility.pending_fees() == fee
    assert strategy_facility.balance == fee

def test_deposit_stake_fee(deployer, strategy, token, staking, weth, strategy_facility):
    strategy_facility.set_fee_rates(100, 0, sender=deployer)
    weth.deposit(value=3 * UNIT, sender=strategy)
    weth.approve(strategy_facility, UNIT, sender=strategy)

    fee = UNIT // 100
    assert weth.balanceOf(strategy) == 3 * UNIT
    assert token.balanceOf(strategy) == 0
    assert strategy_facility.pending_fees() == 0
    assert strategy_facility.balance == 0
    actual = strategy_facility.deposit(UNIT, True, sender=strategy).return_value
    shares = staking.convertToShares(UNIT - fee)
    assert actual == shares
    assert weth.balanceOf(strategy) == 2 * UNIT
    assert staking.balanceOf(strategy) == shares
    assert strategy_facility.pending_fees() == fee
    assert strategy_facility.balance == fee

def test_withdraw(deployer, strategy, token, weth, facility, strategy_facility):
    facility.set_mint_whitelist(deployer, True, sender=deployer)
    facility.mint(value=3 * UNIT, sender=deployer)
    token.transfer(strategy, 3 * UNIT, sender=deployer)
    token.approve(strategy_facility, UNIT, sender=strategy)

    assert weth.balanceOf(strategy) == 0
    assert token.balanceOf(strategy) == 3 * UNIT
    assert strategy_facility.available() == (7 * UNIT, 3 * UNIT)
    assert strategy_facility.withdraw(UNIT, sender=strategy).return_value == UNIT
    assert weth.balanceOf(strategy) == UNIT
    assert token.balanceOf(strategy) == 2 * UNIT
    assert strategy_facility.available() == (8 * UNIT, 2 * UNIT)

def test_withdraw_fee(deployer, strategy, token, weth, facility, strategy_facility):
    strategy_facility.set_fee_rates(0, 100, sender=deployer)
    facility.set_mint_whitelist(deployer, True, sender=deployer)
    facility.mint(value=3 * UNIT, sender=deployer)
    token.transfer(strategy, 3 * UNIT, sender=deployer)
    token.approve(strategy_facility, UNIT, sender=strategy)

    fee = UNIT // 100
    assert weth.balanceOf(strategy) == 0
    assert token.balanceOf(strategy) == 3 * UNIT
    assert strategy_facility.pending_fees() == 0
    assert strategy_facility.balance == 0
    assert strategy_facility.withdraw(UNIT, sender=strategy).return_value == UNIT - fee
    assert weth.balanceOf(strategy) == UNIT - fee
    assert token.balanceOf(strategy) == 2 * UNIT
    assert strategy_facility.pending_fees() == fee
    assert strategy_facility.balance == fee

def test_claim_fees(deployer, alice, operator, strategy, token, weth, strategy_facility):
    weth.deposit(value=3 * UNIT, sender=strategy)
    weth.approve(strategy_facility, 3 * UNIT, sender=strategy)
    token.approve(strategy_facility, UNIT, sender=strategy)
    strategy_facility.deposit(UNIT, False, sender=strategy)
    strategy_facility.set_fee_rates(100, 100, sender=deployer)
    strategy_facility.set_treasury(operator, sender=deployer)

    strategy_facility.deposit(2 * UNIT, False, sender=strategy)
    strategy_facility.withdraw(UNIT, sender=strategy)
    assert strategy_facility.pending_fees() == UNIT * 3 // 100
    bal = operator.balance
    assert strategy_facility.claim_fees(sender=alice).return_value == UNIT * 3 // 100
    assert strategy_facility.pending_fees() == 0
    assert operator.balance == bal + UNIT * 3 // 100

def test_set_fee_rates(deployer, strategy_facility):
    strategy_facility.set_fee_rates(20, 30, sender=deployer)
    assert strategy_facility.fee_rates() == (20, 30)

def test_set_fee_rates_permission(alice, strategy_facility):
    with ape.reverts():
        strategy_facility.set_fee_rates(20, 30, sender=alice)

def test_set_strategy(deployer, alice, strategy, strategy_facility):
    assert strategy_facility.strategy() == strategy
    strategy_facility.set_strategy(alice, sender=deployer)
    assert strategy_facility.strategy() == alice

def test_set_strategy_permission(alice, strategy_facility):
    with ape.reverts():
        strategy_facility.set_strategy(alice, sender=alice)

def test_set_treasury(deployer, alice, strategy_facility):
    assert strategy_facility.treasury() == deployer
    strategy_facility.set_treasury(alice, sender=deployer)
    assert strategy_facility.treasury() == alice

def test_set_treasury_permission(alice, strategy_facility):
    with ape.reverts():
        strategy_facility.set_treasury(alice, sender=alice)

def test_transfer_management(deployer, alice, bob, strategy_facility):
    assert strategy_facility.management() == deployer
    assert strategy_facility.pending_management() == ZERO_ADDRESS

    with ape.reverts():
        strategy_facility.set_management(alice, sender=alice)
    with ape.reverts():
        strategy_facility.accept_management(sender=alice)
 
    strategy_facility.set_management(alice, sender=deployer)
    assert strategy_facility.management() == deployer
    assert strategy_facility.pending_management() == alice

    with ape.reverts():
        strategy_facility.accept_management(sender=bob)
    
    strategy_facility.accept_management(sender=alice)
    assert strategy_facility.management() == alice
    assert strategy_facility.pending_management() == ZERO_ADDRESS
