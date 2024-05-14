import ape
import pytest

ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'
NATIVE = '0x0000000000000000000000000000000000000000'
MINT   = '0x0000000000000000000000000000000000000001'
ONE    = 1_000_000_000_000_000_000
MAX    = 2**256 - 1

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
def token(project, deployer):
    return project.MockToken.deploy(sender=deployer)

@pytest.fixture
def pol(project, deployer, token):
    return project.POL.deploy(token, sender=deployer)

@pytest.fixture
def stake(project, deployer, treasury, pol):
    return project.Stake.deploy(pol, treasury, sender=deployer)

def test_from_pol_native(project, deployer, alice, pol, stake):
    alice.transfer(pol, ONE)
    pol.approve(NATIVE, stake, MAX, sender=deployer)
    with ape.reverts():
        stake.from_pol(NATIVE, ONE, sender=alice)
    assert project.provider.get_balance(stake) == 0
    stake.from_pol(NATIVE, ONE, sender=deployer)
    assert project.provider.get_balance(stake) == ONE

def test_from_pol_token(deployer, alice, token, pol, stake):
    alice.transfer(pol, ONE)
    pol.approve(MINT, deployer, ONE, sender=deployer)
    pol.mint(ONE, sender=deployer)
    pol.approve(token, stake, MAX, sender=deployer)
    
    with ape.reverts():
        stake.from_pol(token, ONE, sender=alice)
    assert token.balanceOf(stake) == 0
    stake.from_pol(token, ONE, sender=deployer)
    assert token.balanceOf(stake) == ONE

def test_to_pol_native(deployer, alice, pol, stake):
    alice.transfer(pol, ONE)
    pol.approve(NATIVE, stake, MAX, sender=deployer)
    stake.from_pol(NATIVE, ONE, sender=deployer)

    assert pol.available() == ONE
    stake.to_pol(NATIVE, ONE, sender=deployer)
    assert pol.available() == ONE

def test_to_pol_token(deployer, alice, token, pol, stake):
    alice.transfer(pol, ONE)
    pol.approve(MINT, deployer, ONE, sender=deployer)
    pol.mint(ONE, sender=deployer)
    pol.approve(token, stake, MAX, sender=deployer)
    stake.from_pol(token, ONE, sender=deployer)

    stake.to_pol(token, ONE, sender=deployer)
    assert token.balanceOf(stake) == 0
    assert token.balanceOf(pol) == ONE

def test_to_treasury_native(deployer, treasury, alice, pol, stake):
    alice.transfer(pol, ONE)
    pol.approve(NATIVE, stake, MAX, sender=deployer)
    stake.from_pol(NATIVE, ONE, sender=deployer)

    pre = treasury.balance
    stake.to_treasury(NATIVE, ONE, sender=deployer)
    assert treasury.balance - pre == ONE

def test_to_treasury_token(deployer, treasury, alice, token, pol, stake):
    alice.transfer(pol, ONE)
    pol.approve(MINT, deployer, ONE, sender=deployer)
    pol.mint(ONE, sender=deployer)
    pol.approve(token, stake, MAX, sender=deployer)
    stake.from_pol(token, ONE, sender=deployer)

    stake.to_treasury(token, ONE, sender=deployer)
    assert token.balanceOf(stake) == 0
    assert token.balanceOf(treasury) == ONE

def test_transfer_management(deployer, alice, bob, stake):
    assert stake.management() == deployer
    assert stake.pending_management() == ZERO_ADDRESS

    with ape.reverts():
        stake.set_management(alice, sender=alice)
    with ape.reverts():
        stake.accept_management(sender=alice)
 
    stake.set_management(alice, sender=deployer)
    assert stake.management() == deployer
    assert stake.pending_management() == alice

    with ape.reverts():
        stake.accept_management(sender=bob)
    
    stake.accept_management(sender=alice)
    assert stake.management() == alice
    assert stake.pending_management() == ZERO_ADDRESS

def test_transfer_treasury(treasury, alice, bob, stake):
    assert stake.treasury() == treasury
    assert stake.pending_treasury() == ZERO_ADDRESS

    with ape.reverts():
        stake.set_treasury(alice, sender=alice)
    with ape.reverts():
        stake.accept_treasury(sender=alice)
 
    stake.set_treasury(alice, sender=treasury)
    assert stake.treasury() == treasury
    assert stake.pending_treasury() == alice

    with ape.reverts():
        stake.accept_treasury(sender=bob)
    
    stake.accept_treasury(sender=alice)
    assert stake.treasury() == alice
    assert stake.pending_treasury() == ZERO_ADDRESS
