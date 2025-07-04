from ape import Contract, reverts
from pytest import fixture

TOKEN = '0x1BED97CBC3c24A4fb5C069C6E311a967386131f7'
OLD_POOL = '0x2cced4ffA804ADbe1269cDFc22D7904471aBdE63'
NEW_POOL = '0x0Ca1bd1301191576Bea9b9afCFD4649dD1Ba6822'
MEVETH = '0x24Ae2dA0f361AA4BE46b48EB19C91e02c5e4f27E'
YCHAD = '0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52'
WETH = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'

NUM_OLD_ASSETS = 8
MEVETH_IDX = 5
UNIT = 10**18

@fixture
def token():
    return Contract(TOKEN)

@fixture
def old():
    return Contract(OLD_POOL)

@fixture
def new():
    return Contract(NEW_POOL)

@fixture
def meveth():
    return Contract(MEVETH)

@fixture
def ychad(accounts):
    return accounts[YCHAD]

@fixture
def weth():
    return Contract(WETH)

@fixture
def governance(networks, accounts, old):
    account = accounts[old.management()]
    networks.active_provider.set_balance(account.address, UNIT)
    return account

@fixture
def management(networks, accounts, new):
    account = accounts[new.management()]
    networks.active_provider.set_balance(account.address, UNIT)
    return account

@fixture
def operator(accounts):
    return accounts[0]

@fixture
def alice(accounts):
    return accounts[1]

@fixture
def migrate(project, governance, management, operator, ychad, token, old, new, meveth):
    migrate = project.Migrate.deploy(token, old, new, meveth, sender=management)
    migrate.set_operator(operator, sender=management)
    new.set_management(migrate, sender=management)
    old.pause(sender=governance)
    old.kill(sender=governance)
    token.set_minter(new, sender=ychad)
    token.set_minter(migrate, sender=ychad)
    return migrate

def test_migrate(networks, accounts, management, operator, ychad, old, new, migrate, token, meveth, weth):
    yeth_amt = old.supply()
    assert yeth_amt > 0 and new.supply() == 0
    assert migrate.debt() == 0
    assert meveth.balanceOf(migrate) == 0
    assert token.balanceOf(migrate) == 0

    balances = []
    for i in range(NUM_OLD_ASSETS):
        if i == MEVETH_IDX:
            continue
        asset = Contract(old.assets(i))
        balances.append(asset.balanceOf(old))

    # migrate
    migrate.migrate(sender=operator)

    migrate_yeth_amt = token.balanceOf(migrate)
    meveth_amt = meveth.balanceOf(migrate)

    assert old.supply() == 0 and new.supply() > 2684 * UNIT
    assert migrate.debt() == yeth_amt
    assert meveth_amt > 587 * UNIT
    assert migrate_yeth_amt > 2684 * UNIT

    dust = 2000
    for i in range(NUM_OLD_ASSETS-1):
        asset = Contract(new.assets(i))
        assert asset.balanceOf(old) < dust
        assert asset.balanceOf(new) > balances[i] - dust

    # repay debt
    migrate.repay(migrate_yeth_amt, sender=operator)
    assert token.balanceOf(migrate) == 0
    assert migrate.debt() < 620 * UNIT

    # queue withdrawal
    meveth_underlying_amt = meveth.convertToAssets(meveth_amt) * 10_000 // 10_001
    id = meveth.queueLength() + 1
    migrate.withdraw(meveth_underlying_amt, sender=operator)
    assert meveth.balanceOf(migrate) <= 2
    assert meveth.queueLength() == id
    assert meveth.withdrawalQueue(id)['receiver'] == management
    
    # finalize withdrawal
    networks.active_provider.set_balance(meveth.address, 1000 * UNIT)
    meveth.processWithdrawalQueue(id, sender=accounts['0x617c8dE5BdE54ffbb8d92716CC947858cA38f582'])
    pre = weth.balanceOf(management)
    meveth.claim(id, sender=operator)
    assert weth.balanceOf(management) - pre >= migrate.debt()

    # withdrawn ETH will be used to buy more LSTs and deposit in new pool
    debt = migrate.debt()
    token.set_minter(ychad, sender=ychad)
    token.mint(ychad, debt, sender=ychad)
    token.set_minter(ychad, False, sender=ychad)
    token.transfer(migrate, debt, sender=ychad)

    migrate.repay(debt, sender=operator)
    assert migrate.debt() == 0

    # revoke minting rights once migration is complete
    token.set_minter(old, False, sender=ychad)
    token.set_minter(migrate, False, sender=ychad)
    assert not token.minters(old) and not token.minters(migrate)

def test_operator_permissions(migrate, operator, alice):
    with reverts():
        migrate.migrate(sender=alice)
    migrate.migrate(sender=operator)

    with reverts():
        migrate.repay(UNIT, sender=alice)
    migrate.repay(UNIT, sender=operator)

    with reverts():
        migrate.withdraw(UNIT, sender=alice)
    migrate.withdraw(UNIT, sender=operator)

def test_management_permissions(migrate, new, meveth, management, operator, alice):
    migrate.migrate(sender=operator)

    with reverts():
        migrate.rescue(meveth, UNIT, sender=alice)
    migrate.rescue(meveth, UNIT, sender=management)
    assert meveth.balanceOf(management) == UNIT

    with reverts():
        migrate.transfer_pool_management(alice, sender=alice)
    migrate.transfer_pool_management(alice, sender=management)
    assert new.pending_management() == alice

    with reverts():
        migrate.set_operator(alice, sender=alice)
    migrate.set_operator(alice, sender=management)
    assert migrate.operator() == alice

    with reverts():
        migrate.set_management(alice, sender=alice)
    with reverts():
        migrate.accept_management(sender=alice)
    migrate.set_management(alice, sender=management)
    assert migrate.pending_management() == alice
    migrate.accept_management(sender=alice)
    assert migrate.management() == alice

def test_rate_provider(project, deployer, old):
    provider = project.V2RateProvider.deploy(sender=deployer)

    for i in range(NUM_OLD_ASSETS):
        if i == MEVETH_IDX:
            continue
        asset = old.assets(i)
        old_provider = Contract(old.rate_providers(i))
        old_rate = old_provider.rate(asset)
        new_rate = provider.rate(asset)
        assert new_rate > 0 and new_rate == old_rate
