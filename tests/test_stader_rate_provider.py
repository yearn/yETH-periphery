from ape import Contract
import pytest

ASSET = '0xA35b1B31Ce002FBF2058D22F30f95D405200A15b'
MANAGER = '0xcf5EA1b38380f6aF39068375516Daf40Ed70D299'
UNIT = 1_000_000_000_000_000_000

@pytest.fixture
def provider(project, deployer):
    return project.StaderRateProvider.deploy(sender=deployer)

def test_oracle_contract(provider, deployer):
    provider.verify_oracle_contract(sender=deployer)

def test_rate_provider(provider):
    rate = provider.rate(ASSET)
    assert rate > UNIT and rate < UNIT * 12 // 10
    manager = Contract(MANAGER)
    assert manager.getExchangeRate() == rate
