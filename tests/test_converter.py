import ape
from ape import Contract
import pytest

POOL = '0x69ACcb968B19a53790f43e57558F5E443A91aF22'
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'
UNIT = 10**18

@pytest.fixture
def operator(accounts):
    return accounts[4]

@pytest.fixture
def weth():
    return Contract('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2')

@pytest.fixture
def yeth():
    return Contract('0x1BED97CBC3c24A4fb5C069C6E311a967386131f7')

@pytest.fixture
def converter(project, deployer, operator, weth, yeth):
    converter = project.Converter.deploy(weth, yeth, sender=deployer)
    converter.set_operator(operator, sender=deployer)
    return converter

def test_convert(deployer, operator, alice, weth, yeth, converter):
    weth.deposit(value=3*UNIT, sender=deployer)
    weth.approve(converter, UNIT, sender=deployer)

    min_out = UNIT * 1001 // 1000

    # permissioned
    with ape.reverts():
        converter.convert(POOL, 0, 1, UNIT, min_out, sender=alice)

    # must be at least 1:1
    with ape.reverts():
        converter.convert(POOL, 0, 1, UNIT, UNIT - 1, sender=operator)

    assert weth.balanceOf(deployer) == 3 * UNIT
    assert yeth.balanceOf(deployer) == 0
    assert weth.balanceOf(converter) == 0
    assert yeth.balanceOf(converter) == 0
    converter.convert(POOL, 0, 1, UNIT, min_out, sender=operator)
    assert weth.balanceOf(deployer) == 2 * UNIT
    assert yeth.balanceOf(deployer) > UNIT
    assert weth.balanceOf(converter) == 0
    assert yeth.balanceOf(converter) == 0

def test_malicious_pool(project, deployer, operator, weth, converter):
    weth.deposit(value=3*UNIT, sender=deployer)
    weth.approve(converter, UNIT, sender=deployer)
    malicious = project.MockMaliciousPool.deploy(weth, sender=deployer)
    with ape.reverts():
        converter.convert(malicious, 0, 1, UNIT, UNIT, sender=operator)
    malicious.set_amount_out(UNIT, sender=deployer)
    with ape.reverts():
        converter.convert(malicious, 0, 1, UNIT, UNIT, sender=operator)
    converter.convert(POOL, 0, 1, UNIT, UNIT, sender=operator)

def test_set_operator(deployer, operator, alice, converter):
    assert converter.operator() == operator
    with ape.reverts():
        converter.set_operator(alice, sender=alice)
    converter.set_operator(alice, sender=deployer)
    assert converter.operator() == alice

def test_set_management(deployer, alice, bob, converter):
    assert converter.management() == deployer
    assert converter.pending_management() == ZERO_ADDRESS
    with ape.reverts():
        converter.set_management(alice, sender=alice)
    with ape.reverts():
        converter.accept_management(sender=alice)
    converter.set_management(alice, sender=deployer)
    assert converter.management() == deployer
    assert converter.pending_management() == alice
    with ape.reverts():
        converter.accept_management(sender=bob)
    converter.accept_management(sender=alice)
    assert converter.management() == alice
    assert converter.pending_management() == ZERO_ADDRESS
