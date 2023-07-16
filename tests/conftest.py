import pytest

@pytest.fixture
def deployer(accounts):
    return accounts[0]
