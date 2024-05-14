from ape import Contract
import pytest

ASSET = '0x93ef1Ea305D11A9b2a3EbB9bB4FCc34695292E7d'
FUND = '0x69c53679EC1C06f3275b64C428e8Cd069a2d3966'
MARKET = '0x8a04A9f1d29C9837604aB4B4c9425098F1DB3f2c'
UNIT = 1_000_000_000_000_000_000

@pytest.fixture
def provider(project, deployer):
    return project.TranchessRateProvider.deploy(sender=deployer)

def test_rate_provider(provider):
    rate = provider.rate(ASSET)
    assert rate > UNIT and rate < UNIT * 12 // 10
    market = Contract(MARKET)
    assert market.getRedemption(UNIT).underlying == rate
