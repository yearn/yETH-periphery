from ape import Contract, reverts
from pytest import fixture

YETH = '0x1BED97CBC3c24A4fb5C069C6E311a967386131f7'
OLD_POOL = '0x0Ca1bd1301191576Bea9b9afCFD4649dD1Ba6822'
NEW_POOL = '0xCcd04073f4BdC4510927ea9Ba350875C3c65BF81'
SWETH = '0xf951E335afb289353dc249e82926178EaC7DEd78'
SWEXIT = '0x48C11b86807627AF70a34662D4865cF854251663'
YCHAD = '0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52'
WETH = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'

OETH = '0x856c4Efb76C1D1AE02e20CEB03A2A6a08b0b8dC3'
WOETH = '0xDcEe70654261AF21C44c093C300eD3Bb97b78192'
METH = '0xd5F7838F5C461fefF7FE49ea5ebaF7728bB0ADfa'

OETH_ZAP = '0x9858e47BCbBe6fBAC040519B02d7cd4B2C470C66'
MANTLE_STAKING = '0xe3cBd06D7dadB3F4e6557bAb7EdD924CD1489E8f'

NUM_OLD_ASSETS = 7
SWETH_IDX = 1
UNIT = 10**18

@fixture
def yeth():
    return Contract(YETH)

@fixture
def old():
    return Contract(OLD_POOL)

@fixture
def new():
    return Contract(NEW_POOL)

@fixture
def sweth():
    return Contract(SWETH)

@fixture
def swexit():
    return Contract(SWEXIT)

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
    networks.active_provider.set_balance(account.address, 100 * UNIT)
    return account

@fixture
def operator(accounts):
    return accounts[0]

@fixture
def alice(accounts):
    return accounts[1]

@fixture
def migrate(project, governance, management, operator, ychad, yeth, old, new, sweth, swexit):
    migrate = project.Migrate2.deploy(yeth, old, new, sweth, swexit, sender=management)
    migrate.set_operator(operator, sender=management)
    new.set_management(migrate, sender=management)
    old.pause(sender=governance)
    old.kill(sender=governance)
    yeth.set_minter(new, sender=ychad)
    yeth.set_minter(migrate, sender=ychad)

    # obtain wOETH
    seed_amt = 35 * UNIT
    zap = Contract(OETH_ZAP)
    zap.deposit(value=seed_amt, sender=management)
    oeth = Contract(OETH)
    woeth = Contract(WOETH)

    oeth.approve(woeth, seed_amt, sender=management)
    woeth.deposit(seed_amt, management, sender=management)
    woeth_amt = woeth.balanceOf(management)
    assert woeth_amt > 30 * UNIT and woeth_amt < 35 * UNIT
    woeth.transfer(migrate, woeth_amt, sender=management)

    # obtain mETH
    mantle_staking = Contract(MANTLE_STAKING)
    mantle_staking.stake(0, value=seed_amt, sender=management)
    meth = Contract(METH)
    meth_amt = meth.balanceOf(management)
    assert meth_amt > 30 * UNIT and meth_amt < 35 * UNIT
    meth.transfer(migrate, meth_amt, sender=management)

    return migrate

def test_migrate(networks, accounts, management, operator, ychad, old, new, migrate, yeth, swexit, sweth):
    yeth_amt = old.supply()
    assert yeth_amt > 0 and new.supply() == 0
    assert migrate.debt() == 0
    assert sweth.balanceOf(migrate) == 0
    assert yeth.balanceOf(migrate) == 0

    balances = []
    for i in range(NUM_OLD_ASSETS):
        if i == SWETH_IDX:
            continue
        asset = Contract(old.assets(i))
        balances.append(asset.balanceOf(old))

    # migrate
    migrate.migrate(sender=operator)

    migrate_yeth_amt = yeth.balanceOf(migrate)
    sweth_amt = sweth.balanceOf(migrate)

    assert old.supply() == 0 and new.supply() > 3486 * UNIT
    assert migrate_yeth_amt == new.supply()
    assert migrate.debt() == yeth_amt
    assert sweth_amt > 492 * UNIT

    dust = 2000
    for i in range(NUM_OLD_ASSETS-1):
        asset = Contract(new.assets(i))
        assert asset.balanceOf(old) < dust
        assert asset.balanceOf(new) > balances[i] - dust

    # repay debt
    migrate.repay(migrate_yeth_amt, sender=operator)
    assert yeth.balanceOf(migrate) == 0
    debt = migrate.debt()
    assert debt < 470 * UNIT
    remain = debt + 70 * UNIT # value of seed

    # queue withdrawal
    migrate.withdraw(sweth_amt, sender=operator)
    id = swexit.getLastTokenIdCreated()
    assert sweth.balanceOf(migrate) == 0
    assert swexit.ownerOf(id) == migrate
    w = swexit.withdrawalRequests(id)
    assert w['amount'] == sweth_amt
    assert w['amount'] * w['rateWhenCreated'] // UNIT >= remain

    # finalize withdrawal
    migrate.swexit_transfer(id, sender=operator)
    assert swexit.ownerOf(id) == management
    networks.active_provider.set_balance('0xb3D9cf8E163bbc840195a97E81F8A34E295B8f39', 1_000_000 * UNIT)
    oracle = accounts['0x289d600447A74B952AD16F0BD53b8eaAac2d2D71']
    networks.active_provider.set_balance(oracle.address, UNIT)
    swexit.processWithdrawals(id, sender=oracle)
    pre = management.balance
    swexit.finalizeWithdrawal(id, sender=management)
    eth_amt = management.balance - pre
    assert eth_amt >= remain

    # withdrawn ETH will be used to repay POL and buy more LSTs to deposit in new pool
    yeth.set_minter(ychad, sender=ychad)
    yeth.mint(ychad, debt, sender=ychad)
    yeth.set_minter(ychad, False, sender=ychad)
    yeth.transfer(migrate, debt, sender=ychad)

    migrate.repay(debt, sender=operator)
    assert migrate.debt() == 0

    # revoke minting rights once migration is complete
    yeth.set_minter(old, False, sender=ychad)
    yeth.set_minter(migrate, False, sender=ychad)
    assert not yeth.minters(old) and not yeth.minters(migrate)

def test_operator_permissions(migrate, swexit, operator, alice):
    with reverts():
        migrate.migrate(sender=alice)
    migrate.migrate(sender=operator)

    with reverts():
        migrate.repay(UNIT, sender=alice)
    migrate.repay(UNIT, sender=operator)

    with reverts():
        migrate.withdraw(UNIT, sender=alice)
    migrate.withdraw(UNIT, sender=operator)
    id = swexit.getLastTokenIdCreated()

    with reverts():
        migrate.swexit_transfer(id, sender=alice)
    migrate.swexit_transfer(id, sender=operator)

def test_management_permissions(migrate, new, sweth, management, operator, alice):
    migrate.migrate(sender=operator)

    with reverts():
        migrate.rescue(sweth, UNIT, sender=alice)
    migrate.rescue(sweth, UNIT, sender=management)
    assert sweth.balanceOf(management) == UNIT

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
    provider = project.V3RateProvider.deploy(sender=deployer)

    for i in range(NUM_OLD_ASSETS):
        if i == SWETH_IDX:
            continue
        asset = Contract(old.assets(i))
        old_provider = Contract(old.rate_providers(i))
        old_rate = old_provider.rate(asset)
        new_rate = provider.rate(asset)
        assert new_rate > 0 and new_rate == old_rate
    assert provider.rate(WOETH) > 113 * UNIT // 100 and provider.rate(WOETH) < 114 * UNIT // 100
    assert provider.rate(METH) > 106 * UNIT // 100 and provider.rate(METH) < 107 * UNIT // 100
