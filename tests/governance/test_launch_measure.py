import ape
import pytest

STAKING = '0x583019fF0f430721aDa9cfb4fac8F06cA104d0B4'
BOOTSTRAP = '0x7cf484D9d16BA26aB3bCdc8EC4a73aC50136d491'
YCHAD = '0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52'

@pytest.fixture
def staking():
    return ape.Contract(STAKING)

@pytest.fixture
def bootstrap():
    return ape.Contract(BOOTSTRAP)

@pytest.fixture
def measure(project, deployer, staking, bootstrap):
    return project.LaunchMeasure.deploy(staking, bootstrap, sender=deployer)

def test_bootstrap_weight(staking, bootstrap, measure):
    weight = measure.vote_weight(YCHAD)
    assert weight > 0
    assert weight == staking.vote_weight(bootstrap) * bootstrap.deposits(YCHAD) // bootstrap.deposited()
