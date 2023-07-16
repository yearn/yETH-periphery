from ape import Contract
import pytest

ASSET = '0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0'
UNDERLYING = '0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84'
UNIT = 1_000_000_000_000_000_000

@pytest.fixture
def provider(project, deployer):
    return project.LidoRateProvider.deploy(sender=deployer)

def test_rate_provider(project, provider, accounts):
    asset = Contract(ASSET)
    rate = provider.rate(ASSET)
    assert rate > UNIT and rate < UNIT * 12 // 10
    assert asset.stEthPerToken() == rate

    account = accounts['0x248cCBf4864221fC0E840F29BB042ad5bFC89B5c']
    asset.unwrap(UNIT, sender=account)
    assert abs(Contract(UNDERLYING).balanceOf(account) - rate) <= 1 # rounding
