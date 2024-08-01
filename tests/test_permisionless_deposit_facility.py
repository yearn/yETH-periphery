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
def token():
    return Contract('0x1BED97CBC3c24A4fb5C069C6E311a967386131f7')

@pytest.fixture
def staking():
    return Contract('0x583019fF0f430721aDa9cfb4fac8F06cA104d0B4')

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
def permissionless_facility(project, deployer, token, staking, facility):
    permissionless_facility = project.PermissionlessDepositFacility.deploy(token, staking, facility, sender=deployer)
    facility.set_mint_whitelist(permissionless_facility, True, sender=deployer)
    facility.set_burn_whitelist(permissionless_facility, True, sender=deployer)
    return permissionless_facility

def test_send(alice, token, permissionless_facility):
    assert token.balanceOf(alice) == 0
    assert permissionless_facility.available() == (10 * UNIT, 0)
    alice.transfer(permissionless_facility, UNIT)
    assert token.balanceOf(alice) == UNIT
    assert permissionless_facility.available() == (9 * UNIT, UNIT)

def test_deposit(alice, bob, token, permissionless_facility):
    assert token.balanceOf(bob) == 0
    assert permissionless_facility.available() == (10 * UNIT, 0)
    assert permissionless_facility.deposit(False, bob, sender=alice, value=UNIT).return_value == UNIT
    assert token.balanceOf(bob) == UNIT
    assert permissionless_facility.available() == (9 * UNIT, UNIT)

def test_deposit_stake(alice, bob, staking, permissionless_facility):
    assert staking.balanceOf(bob) == 0
    actual = permissionless_facility.deposit(True, bob, value=UNIT, sender=alice).return_value
    shares = staking.convertToShares(UNIT)
    assert actual == shares
    assert staking.balanceOf(bob) == shares

def test_deposit_fee(deployer, alice, token, permissionless_facility):
    permissionless_facility.set_fee_rates(100, 0, sender=deployer)

    fee = UNIT // 100
    assert token.balanceOf(alice) == 0
    assert permissionless_facility.pending_fees() == 0
    assert permissionless_facility.balance == 0
    assert permissionless_facility.deposit(False, value=UNIT, sender=alice).return_value == UNIT - fee
    assert token.balanceOf(alice) == UNIT - fee
    assert permissionless_facility.pending_fees() == fee
    assert permissionless_facility.balance == fee

def test_deposit_stake_fee(deployer, alice, token, staking, permissionless_facility):
    permissionless_facility.set_fee_rates(100, 0, sender=deployer)

    fee = UNIT // 100
    assert token.balanceOf(alice) == 0
    assert permissionless_facility.pending_fees() == 0
    assert permissionless_facility.balance == 0
    actual = permissionless_facility.deposit(value=UNIT, sender=alice).return_value
    shares = staking.convertToShares(UNIT - fee)
    assert actual == shares
    assert staking.balanceOf(alice) == shares
    assert permissionless_facility.pending_fees() == fee
    assert permissionless_facility.balance == fee

def test_withdraw(deployer, alice, bob, token, facility, permissionless_facility):
    facility.set_mint_whitelist(deployer, True, sender=deployer)
    facility.mint(value=3 * UNIT, sender=deployer)

    token.transfer(alice, 3 * UNIT, sender=deployer)
    token.approve(permissionless_facility, UNIT, sender=alice)

    assert token.balanceOf(alice) == 3 * UNIT
    assert permissionless_facility.available() == (7 * UNIT, 3 * UNIT)
    pre = bob.balance
    assert permissionless_facility.withdraw(UNIT, bob, sender=alice).return_value == UNIT
    assert bob.balance - pre == UNIT
    assert token.balanceOf(alice) == 2 * UNIT
    assert permissionless_facility.available() == (8 * UNIT, 2 * UNIT)

def test_withdraw_fee(deployer, alice, bob, token, facility, permissionless_facility):
    permissionless_facility.set_fee_rates(0, 100, sender=deployer)
    facility.set_mint_whitelist(deployer, True, sender=deployer)
    facility.mint(value=3 * UNIT, sender=deployer)
    token.transfer(alice, 3 * UNIT, sender=deployer)
    token.approve(permissionless_facility, UNIT, sender=alice)

    fee = UNIT // 100
    assert token.balanceOf(alice) == 3 * UNIT
    assert permissionless_facility.pending_fees() == 0
    assert permissionless_facility.balance == 0
    pre = bob.balance
    assert permissionless_facility.withdraw(UNIT, bob, sender=alice).return_value == UNIT - fee
    assert bob.balance - pre == UNIT - fee
    assert token.balanceOf(alice) == 2 * UNIT
    assert permissionless_facility.pending_fees() == fee
    assert permissionless_facility.balance == fee

def test_claim_fees(deployer, alice, operator, token, permissionless_facility):
    token.approve(permissionless_facility, UNIT, sender=alice)
    permissionless_facility.deposit(False, value=UNIT, sender=alice)
    permissionless_facility.set_fee_rates(100, 100, sender=deployer)
    permissionless_facility.set_treasury(operator, sender=deployer)

    permissionless_facility.deposit(False, value=2*UNIT, sender=alice)
    permissionless_facility.withdraw(UNIT, sender=alice)
    assert permissionless_facility.pending_fees() == UNIT * 3 // 100
    bal = operator.balance
    assert permissionless_facility.claim_fees(sender=alice).return_value == UNIT * 3 // 100
    assert permissionless_facility.pending_fees() == 0
    assert operator.balance == bal + UNIT * 3 // 100

def test_set_fee_rates(deployer, permissionless_facility):
    permissionless_facility.set_fee_rates(20, 30, sender=deployer)
    assert permissionless_facility.fee_rates() == (20, 30)

def test_set_fee_rates_permission(alice, permissionless_facility):
    with ape.reverts():
        permissionless_facility.set_fee_rates(20, 30, sender=alice)

def test_set_treasury(deployer, alice, permissionless_facility):
    assert permissionless_facility.treasury() == deployer
    permissionless_facility.set_treasury(alice, sender=deployer)
    assert permissionless_facility.treasury() == alice

def test_set_treasury_permission(alice, permissionless_facility):
    with ape.reverts():
        permissionless_facility.set_treasury(alice, sender=alice)

def test_transfer_management(deployer, alice, bob, permissionless_facility):
    assert permissionless_facility.management() == deployer
    assert permissionless_facility.pending_management() == ZERO_ADDRESS

    with ape.reverts():
        permissionless_facility.set_management(alice, sender=alice)
    with ape.reverts():
        permissionless_facility.accept_management(sender=alice)
 
    permissionless_facility.set_management(alice, sender=deployer)
    assert permissionless_facility.management() == deployer
    assert permissionless_facility.pending_management() == alice

    with ape.reverts():
        permissionless_facility.accept_management(sender=bob)
    
    permissionless_facility.accept_management(sender=alice)
    assert permissionless_facility.management() == alice
    assert permissionless_facility.pending_management() == ZERO_ADDRESS
