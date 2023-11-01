from ape import Contract
import pytest

ASSET = '0x24Ae2dA0f361AA4BE46b48EB19C91e02c5e4f27E'
UNIT = 1_000_000_000_000_000_000

@pytest.fixture
def provider(project, deployer):
    return project.MevProtocolRateProvider.deploy(sender=deployer)

def test_rate_provider(provider, accounts):
    asset = Contract(ASSET)
    before = provider.rate(ASSET)
    vault = accounts[asset.mevEthShareVault()]
    accounts[0].transfer(vault, 10 * UNIT)
    asset.grantRewards(value=10*UNIT, sender=vault)
    rate = provider.rate(ASSET)
    assert rate > before

    admin = accounts['0xe60f7016247218D2d4662f6623722221990993de']
    asset.setMinWithdrawal(0, sender=admin)
    
    account = accounts['0x6D5a7597896A703Fe8c85775B23395a48f971305']
    asset.redeem(UNIT, accounts[0], account, sender=account)
    weth = Contract('0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2')
    assert weth.balanceOf(accounts[0]) == rate * 9999 // 10000
