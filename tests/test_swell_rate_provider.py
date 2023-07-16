from ape import Contract
import pytest

ASSET = '0xf951E335afb289353dc249e82926178EaC7DEd78'
UNIT = 1_000_000_000_000_000_000

@pytest.fixture
def provider(project, deployer):
    return project.SwellRateProvider.deploy(sender=deployer)

def test_rate_provider(provider):
    asset = Contract(ASSET)
    rate = provider.rate(ASSET)
    assert rate > UNIT and rate < UNIT * 12 // 10
    assert asset.getRate() == rate
