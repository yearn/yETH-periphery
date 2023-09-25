import pytest

@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def alice(accounts):
    return accounts[1]

@pytest.fixture
def bob(accounts):
    return accounts[2]

@pytest.fixture
def charlie(accounts):
    return accounts[3]
