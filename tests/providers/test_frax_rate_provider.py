from ape import Contract
import pytest

ASSET = '0xac3E018457B222d93114458476f3E3416Abbe38F'
UNDERLYING = '0x5E8422345238F34275888049021821E8E08CAa1f'
UNIT = 1_000_000_000_000_000_000

@pytest.fixture
def provider(project, deployer):
    return project.FraxRateProvider.deploy(sender=deployer)

def test_rate_provider(provider, accounts):
    asset = Contract(ASSET)
    account = accounts['0x78bB3aEC3d855431bd9289fD98dA13F9ebB7ef15']
    underlying = Contract(UNDERLYING)
    asset.redeem(UNIT, accounts[0], account, sender=account)

    rate = provider.rate(ASSET)
    assert rate > UNIT and rate < UNIT * 12 // 10
    assert asset.pricePerShare() == rate
    assert underlying.balanceOf(accounts[0]) == rate
