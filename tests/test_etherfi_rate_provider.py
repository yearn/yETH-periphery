from ape import Contract
import pytest

ASSET = '0xCd5fE23C85820F7B72D0926FC9b05b43E359b7ee'
UNDERLYING = '0x35fA164735182de50811E8e2E824cFb9B6118ac2'
UNIT = 1_000_000_000_000_000_000

@pytest.fixture
def provider(project, deployer):
    return project.EtherFiRateProvider.deploy(sender=deployer)

def test_rate_provider(provider, accounts):
    asset = Contract(ASSET)
    account = accounts['0x2b0024ecee0626E9cFB5F0195F69DCaC5b759Dc9']
    underlying = Contract(UNDERLYING)
    rate = provider.rate(ASSET)
    asset.unwrap(UNIT, sender=account)
    assert rate > UNIT and rate < UNIT * 12 // 10
    assert abs(underlying.balanceOf(account) - rate) <= 1 # rounding difference due to rebase mechanism
