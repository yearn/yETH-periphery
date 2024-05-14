from ape import Contract
import pytest

ASSET = '0x9Ba021B0a9b958B5E75cE9f6dff97C7eE52cb3E6'
UNDERLYING = '0x04C154b66CB340F3Ae24111CC767e0184Ed00Cc6'
UNIT = 1_000_000_000_000_000_000

@pytest.fixture
def provider(project, deployer):
    return project.PirexRateProvider.deploy(sender=deployer)

def test_rate_provider(provider, accounts):
    asset = Contract(ASSET)
    account = accounts['0x3A8EAF3fE0082e478293917F2E81F4fEED97ace2']
    underlying = Contract(UNDERLYING)
    asset.redeem(UNIT, accounts[0], account, sender=account)

    rate = provider.rate(ASSET)
    assert rate > UNIT and rate < UNIT * 12 // 10
    assert underlying.balanceOf(accounts[0]) == rate
