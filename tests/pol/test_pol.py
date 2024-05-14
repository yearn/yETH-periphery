import ape
import pytest

ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'
NATIVE = '0x0000000000000000000000000000000000000000'
MINT   = '0x0000000000000000000000000000000000000001'
BURN   = '0x0000000000000000000000000000000000000002'
ONE    = 1_000_000_000_000_000_000
MAX    = 2**256 - 1

@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def alice(accounts):
    return accounts[1]

@pytest.fixture
def bob(accounts):
    return accounts[2]

@pytest.fixture
def token(project, deployer):
    return project.MockToken.deploy(sender=deployer)

@pytest.fixture
def pol(project, deployer, token):
    return project.POL.deploy(token, sender=deployer)

def test_approve_privilege(deployer, alice, pol):
    with ape.reverts():
        pol.approve(MINT, alice, ONE, sender=alice)
    with ape.reverts():
        pol.increase_allowance(MINT, alice, ONE, sender=alice)
    pol.approve(MINT, alice, ONE, sender=deployer)
    with ape.reverts():
        pol.decrease_allowance(MINT, alice, ONE, sender=alice)

def test_native_no_allowance(alice, bob, pol):
    with ape.reverts():
        pol.send_native(bob, ONE, sender=alice)

def test_native(deployer, alice, bob, pol):
    deployer.transfer(pol, ONE)
    assert pol.native_allowance(alice) == 0
    pol.approve(NATIVE, alice, 3 * ONE, sender=deployer)
    assert pol.native_allowance(alice) == 3 * ONE
    pre = bob.balance
    pol.send_native(bob, ONE, sender=alice)
    assert pol.native_allowance(alice) == 2 * ONE
    assert bob.balance - pre == ONE

def test_native_increase(deployer, alice, pol):
    pol.approve(NATIVE, alice, ONE, sender=deployer)
    pol.increase_allowance(NATIVE, alice, 2 * ONE, sender=deployer)
    assert pol.native_allowance(alice) == 3 * ONE

def test_native_decrease(deployer, alice, pol):
    pol.approve(NATIVE, alice, 3 * ONE, sender=deployer)
    pol.decrease_allowance(NATIVE, alice, ONE, sender=deployer)
    assert pol.native_allowance(alice) == 2 * ONE

def test_mint_no_allowance(deployer, alice, pol):
    deployer.transfer(pol, ONE)
    with ape.reverts():
        pol.mint(ONE, sender=alice)

def test_mint_debt_ceiling(deployer, alice, pol):
    deployer.transfer(pol, ONE)
    pol.approve(MINT, alice, 2 * ONE, sender=deployer)
    with ape.reverts():
        pol.mint(2 * ONE, sender=alice)

def test_mint(deployer, alice, token, pol):
    deployer.transfer(pol, ONE)
    assert pol.mint_allowance(alice) == 0
    assert pol.debt() == 0
    pol.approve(MINT, alice, 3 * ONE, sender=deployer)
    assert pol.mint_allowance(alice) == 3 * ONE
    pol.mint(ONE, sender=alice)
    assert pol.mint_allowance(alice) == 2 * ONE
    assert pol.debt() == ONE
    assert token.balanceOf(pol) == ONE

def test_mint_increase(deployer, alice, pol):
    pol.approve(MINT, alice, ONE, sender=deployer)
    pol.increase_allowance(MINT, alice, 2 * ONE, sender=deployer)
    assert pol.mint_allowance(alice) == 3 * ONE

def test_mint_decrease(deployer, alice, pol):
    pol.approve(MINT, alice, 3 * ONE, sender=deployer)
    pol.decrease_allowance(MINT, alice, ONE, sender=deployer)
    assert pol.mint_allowance(alice) == 2 * ONE

def test_burn_no_allowance(deployer, alice, pol):
    deployer.transfer(pol, ONE)
    pol.approve(MINT, alice, ONE, sender=deployer)
    pol.mint(ONE, sender=alice)
    with ape.reverts():
        pol.burn(ONE, sender=alice)

def test_burn(deployer, alice, token, pol):
    deployer.transfer(pol, ONE)
    pol.approve(MINT, alice, ONE, sender=deployer)
    pol.mint(ONE, sender=alice)
    assert pol.burn_allowance(alice) == 0
    pol.approve(BURN, alice, 3 * ONE, sender=deployer)
    assert pol.burn_allowance(alice) == 3 * ONE
    pol.burn(ONE, sender=alice)
    assert pol.burn_allowance(alice) == 2 * ONE
    assert pol.debt() == 0
    assert token.balanceOf(pol) == 0

def test_burn_increase(deployer, alice, pol):
    pol.approve(BURN, alice, ONE, sender=deployer)
    pol.increase_allowance(BURN, alice, 2 * ONE, sender=deployer)
    assert pol.burn_allowance(alice) == 3 * ONE

def test_burn_decrease(deployer, alice, pol):
    pol.approve(BURN, alice, 3 * ONE, sender=deployer)
    pol.decrease_allowance(BURN, alice, ONE, sender=deployer)
    assert pol.burn_allowance(alice) == 2 * ONE

def test_allow(project, deployer, alice, pol):
    token = project.MockToken.deploy(sender=deployer)
    assert token.allowance(pol, alice) == 0
    pol.approve(token, alice, ONE, sender=deployer)
    assert token.allowance(pol, alice) == ONE

def test_allow_increase(project, deployer, alice, pol):
    token = project.MockToken.deploy(sender=deployer)
    pol.approve(token, alice, ONE, sender=deployer)
    pol.increase_allowance(token, alice, 2 * ONE, sender=deployer)
    assert token.allowance(pol, alice) == 3 * ONE

def test_allow_decrease(project, deployer, alice, pol):
    token = project.MockToken.deploy(sender=deployer)
    pol.approve(token, alice, 3 * ONE, sender=deployer)
    pol.decrease_allowance(token, alice, ONE, sender=deployer)
    assert token.allowance(pol, alice) == 2 * ONE

def test_transfer_management(deployer, alice, bob, pol):
    assert pol.management() == deployer
    assert pol.pending_management() == ZERO_ADDRESS

    with ape.reverts():
        pol.set_management(alice, sender=alice)
    with ape.reverts():
        pol.accept_management(sender=alice)
 
    pol.set_management(alice, sender=deployer)
    assert pol.management() == deployer
    assert pol.pending_management() == alice

    with ape.reverts():
        pol.accept_management(sender=bob)
    
    pol.accept_management(sender=alice)
    assert pol.management() == alice
    assert pol.pending_management() == ZERO_ADDRESS
