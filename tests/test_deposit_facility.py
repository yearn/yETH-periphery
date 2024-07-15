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
    management = accounts[token.management()]
    token.set_minter(facility, sender=management)
    return facility

def test_mint(deployer, alice, bob, token, facility):
    facility.set_mint_whitelist(alice, True, sender=deployer)
    facility.set_capacity(3 * UNIT, sender=deployer)
    assert facility.debt() == 0
    assert facility.available()[0] == 3 * UNIT
    assert token.balanceOf(bob) == 0
    facility.mint(bob, sender=alice, value=UNIT)
    assert facility.debt() == UNIT
    assert facility.available()[0] == 2 * UNIT
    assert token.balanceOf(bob) == UNIT

def test_mint_capacity(deployer, alice, facility):
    facility.set_mint_whitelist(alice, True, sender=deployer)
    facility.set_capacity(UNIT, sender=deployer)
    facility.mint(sender=alice, value=UNIT)
    assert facility.available()[0] == 0
    with ape.reverts():
        facility.mint(sender=alice, value=UNIT)

def test_mint_permission(deployer, alice, facility):
    facility.set_capacity(3 * UNIT, sender=deployer)
    with ape.reverts():
        facility.mint(sender=alice, value=UNIT)

def test_burn(deployer, alice, bob, token, facility):
    facility.set_mint_whitelist(alice, True, sender=deployer)
    facility.set_burn_whitelist(alice, True, sender=deployer)
    facility.set_capacity(7 * UNIT, sender=deployer)
    facility.mint(sender=alice, value=3 * UNIT)
    assert facility.debt() == 3 * UNIT
    assert facility.available() == (4 * UNIT, 3 * UNIT)
    assert token.balanceOf(alice) == 3 * UNIT
    pre = bob.balance
    facility.burn(UNIT, bob, sender=alice)
    assert facility.debt() == 2 * UNIT
    assert facility.available() == (5 * UNIT, 2 * UNIT)
    assert token.balanceOf(alice) == 2 * UNIT
    assert bob.balance == pre + UNIT

def test_burn_permission(deployer, alice, facility):
    facility.set_mint_whitelist(alice, True, sender=deployer)
    facility.set_capacity(UNIT, sender=deployer)
    facility.mint(sender=alice, value=UNIT)
    with ape.reverts():
        facility.burn(UNIT, sender=alice)

def test_from_pol(deployer, alice, operator, pol, facility):
    alice.transfer(pol, 3 * UNIT)
    pol.increase_allowance(NATIVE, facility, UNIT, sender=deployer)
    assert pol.balance == 3 * UNIT
    assert facility.balance == 0
    assert facility.pol_debt() == 0
    facility.from_pol(UNIT, sender=operator)
    assert pol.balance == 2 * UNIT
    assert facility.balance == UNIT
    assert facility.pol_debt() == UNIT

def test_from_pol_permission(deployer, alice, pol, facility):
    alice.transfer(pol, 3 * UNIT)
    pol.increase_allowance(NATIVE, facility, UNIT, sender=deployer)
    with ape.reverts():
        facility.from_pol(UNIT, sender=alice)

def test_to_pol_no_debt(deployer, alice, operator, pol, facility):
    facility.set_mint_whitelist(alice, True, sender=deployer)
    facility.set_capacity(3 * UNIT, sender=deployer)
    facility.mint(value=3 * UNIT, sender=alice)
    assert facility.balance == 3 * UNIT
    assert facility.available()[1] == 3 * UNIT
    assert pol.balance == 0
    assert pol.available() == 0
    facility.to_pol(UNIT, sender=operator)
    assert facility.balance == 2 * UNIT
    assert facility.available()[1] == 2 * UNIT
    assert pol.balance == UNIT
    assert pol.available() == UNIT

def test_to_pol_debt(deployer, alice, operator, pol, facility):
    alice.transfer(pol, 3 * UNIT)
    pol.increase_allowance(NATIVE, facility, 3 * UNIT, sender=deployer)
    facility.from_pol(3 * UNIT, sender=operator)
    assert facility.balance == 3 * UNIT
    assert facility.pol_debt() == 3 * UNIT
    assert facility.available()[1] == 3 * UNIT
    assert pol.balance == 0
    assert pol.available() == 3 * UNIT
    facility.to_pol(UNIT, sender=operator)
    assert facility.balance == 2 * UNIT
    assert facility.pol_debt() == 2 * UNIT
    assert facility.available()[1] == 2 * UNIT
    assert pol.balance == UNIT
    assert pol.available() == 3 * UNIT

def test_to_pol_partial_debt(deployer, alice, operator, pol, facility):
    alice.transfer(pol, UNIT)
    pol.increase_allowance(NATIVE, facility, UNIT, sender=deployer)
    facility.from_pol(UNIT, sender=operator)
    facility.set_mint_whitelist(alice, True, sender=deployer)
    facility.set_capacity(3 * UNIT, sender=deployer)
    facility.mint(value=3 * UNIT, sender=alice)
    assert facility.balance == 4 * UNIT
    assert facility.pol_debt() == UNIT
    assert facility.available()[1] == 4 * UNIT
    assert pol.balance == 0
    assert pol.available() == UNIT
    facility.to_pol(3 * UNIT, sender=operator)
    assert facility.balance == UNIT
    assert facility.pol_debt() == 0
    assert facility.available()[1] == UNIT
    assert pol.balance == 3 * UNIT
    assert pol.available() == 3 * UNIT

def test_to_pol_permission(deployer, alice, facility):
    facility.set_mint_whitelist(alice, True, sender=deployer)
    facility.set_capacity(3 * UNIT, sender=deployer)
    facility.mint(value=3 * UNIT, sender=alice)
    with ape.reverts():
        facility.to_pol(UNIT, sender=alice)

def test_set_capacity(deployer, facility):
    assert facility.capacity() == 0
    facility.set_capacity(UNIT, sender=deployer)
    assert facility.capacity() == UNIT
    assert facility.available()[0] == UNIT

def test_set_capacity_permission(alice, facility):
    with ape.reverts():
        facility.set_capacity(UNIT, sender=alice)

def test_set_mint_whitelist(deployer, alice, facility):
    assert not facility.mint_whitelist(alice)
    facility.set_mint_whitelist(alice, True, sender=deployer)
    assert facility.mint_whitelist(alice)
    facility.set_mint_whitelist(alice, False, sender=deployer)
    assert not facility.mint_whitelist(alice)

def test_set_mint_whitelist_permission(alice, facility):
    with ape.reverts():
        facility.set_mint_whitelist(alice, True, sender=alice)

def test_set_burn_whitelist(deployer, alice, facility):
    assert not facility.burn_whitelist(alice)
    facility.set_burn_whitelist(alice, True, sender=deployer)
    assert facility.burn_whitelist(alice)
    facility.set_burn_whitelist(alice, False, sender=deployer)
    assert not facility.burn_whitelist(alice)

def test_set_burn_whitelist_permission(alice, facility):
    with ape.reverts():
        facility.set_burn_whitelist(alice, True, sender=alice)

def test_set_operator(deployer, alice, operator, facility):
    assert facility.operator() == operator
    facility.set_operator(alice, sender=deployer)
    assert facility.operator() == alice

def test_set_operator_permission(alice, facility):
    with ape.reverts():
        facility.set_operator(alice, sender=alice)

def test_set_pol(deployer, alice, pol, facility):
    assert facility.pol() == pol
    facility.set_pol(alice, sender=deployer)
    assert facility.pol() == alice

def test_set_pol_permission(alice, facility):
    with ape.reverts():
        facility.set_pol(alice, sender=alice)

def test_transfer_management(deployer, alice, bob, facility):
    assert facility.management() == deployer
    assert facility.pending_management() == ZERO_ADDRESS

    with ape.reverts():
        facility.set_management(alice, sender=alice)
    with ape.reverts():
        facility.accept_management(sender=alice)
 
    facility.set_management(alice, sender=deployer)
    assert facility.management() == deployer
    assert facility.pending_management() == alice

    with ape.reverts():
        facility.accept_management(sender=bob)
    
    facility.accept_management(sender=alice)
    assert facility.management() == alice
    assert facility.pending_management() == ZERO_ADDRESS
