from ape import Contract
import pytest

ASSET = '0x9559Aaa82d9649C7A7b220E7c461d2E74c9a3593'
UNIT = 1_000_000_000_000_000_000

@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def provider(project, deployer):
    return project.StaFiRateProvider.deploy(sender=deployer)

def test_balances_contract(provider, deployer):
    assert provider.verify_balances_contract(sender=deployer)

def test_rate_provider(provider, accounts):
    deposit = Contract('0xc12dfb80d80d564DB9b180AbF61a252eE6355058')
    deposit.deposit(value=10 * UNIT, sender=accounts[0])

    account = accounts['0xBA12222222228d8Ba445958a75a0704d566BF2C8']
    asset = Contract(ASSET)
    asset.setBurnEnabled(True, sender=accounts['0x211BEd4bd65d4c01643377d95491B8c4B533EAAD'])

    rate = provider.rate(ASSET)
    assert rate > UNIT and rate < UNIT * 12 // 10
    assert Contract(ASSET).getExchangeRate() == rate

    asset.userBurn(UNIT, sender=account)
    assert account.balance == rate
