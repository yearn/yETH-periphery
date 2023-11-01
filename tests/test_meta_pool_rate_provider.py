from ape import Contract
import pytest

ASSET = '0x48AFbBd342F64EF8a9Ab1C143719b63C2AD81710'
UNIT = 1_000_000_000_000_000_000

@pytest.fixture
def provider(project, deployer):
    return project.MetaPoolRateProvider.deploy(sender=deployer)

def test_rate_provider(provider, accounts):
    account = accounts['0x49A323CC2fa5F9A138f30794B9348e43065D8dA2']
    asset = Contract(ASSET)
    asset.transfer(accounts[0], UNIT, sender=account)
    asset.redeem(UNIT, accounts[0], accounts[0], sender=accounts[0])
    rate = provider.rate(ASSET)
    withdrawal = Contract(asset.withdrawal())
    assert withdrawal.pendingWithdraws(accounts[0]).amount == rate
