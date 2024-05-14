from ape import Contract
import pytest

ASSET = '0xae78736Cd615f374D3085123A210448E74Fc6393'
UNIT = 1_000_000_000_000_000_000

@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def provider(project, deployer):
    return project.RocketPoolRateProvider.deploy(sender=deployer)

def test_balances_contract(provider, deployer):
    assert provider.verify_balances_contract(sender=deployer)

def test_rate_provider(provider, accounts):
    asset = Contract(ASSET)
    rate = provider.rate(ASSET)
    assert Contract(ASSET).getExchangeRate() == rate

    account = accounts['0xCc9EE9483f662091a1de4795249E24aC0aC2630f']
    asset.transfer(accounts[0], UNIT, sender=account)
    before = accounts[0].balance
    asset.burn(UNIT, sender=accounts[0])
    assert accounts[0].balance - before == rate
