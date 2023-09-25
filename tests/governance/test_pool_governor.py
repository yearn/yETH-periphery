import ape
import pytest

WEEK = 7 * 24 * 60 * 60
VOTE_START = 3 * WEEK
EPOCH_LENGTH = 4 * WEEK
UNIT = 1_000_000_000_000_000_000
ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'
POOL = '0x2cced4ffA804ADbe1269cDFc22D7904471aBdE63'
YETH = '0x1BED97CBC3c24A4fb5C069C6E311a967386131f7'
APPLICATION_DISABLED = '0x0000000000000000000000000000000000000001'

@pytest.fixture
def measure(project, deployer):
    return project.MockMeasure.deploy(sender=deployer)

@pytest.fixture
def proxy(project, deployer):
    return project.OwnershipProxy.deploy(sender=deployer)

@pytest.fixture
def executor(project, deployer, proxy):
    executor = project.Executor.deploy(proxy, sender=deployer)
    data = proxy.set_management.encode_input(executor)
    proxy.execute(proxy, data, sender=deployer)
    return executor

@pytest.fixture
def candidate(project, deployer):
    return project.MockToken.deploy(sender=deployer)

@pytest.fixture
def fee_token(project, deployer):
    return project.MockToken.deploy(sender=deployer)

@pytest.fixture
def ivoting(chain, project, deployer, measure, fee_token):
    return project.InclusionVote.deploy(chain.pending_timestamp - EPOCH_LENGTH, measure, fee_token, sender=deployer)

@pytest.fixture
def tokens(project, deployer):
    return [project.MockToken.deploy(sender=deployer) for _ in range(2)]

@pytest.fixture
def lp_token(chain, deployer):
    deployed = ape.Contract(YETH)
    return chain.contracts.get_container(deployed.contract_type).deploy(sender=deployer)

@pytest.fixture
def provider(project, deployer, tokens):
    provider = project.MockProvider.deploy(sender=deployer)
    for token in tokens:
        provider.set_rate(token, UNIT, sender=deployer)
    return provider

@pytest.fixture
def pool(chain, deployer, alice, proxy, executor, tokens, lp_token, provider):
    deployed = ape.Contract(POOL)
    pool = chain.contracts.get_container(deployed.contract_type).deploy(
        lp_token, 450 * UNIT, tokens, [provider for _ in tokens], [UNIT//len(tokens) for _ in tokens], sender=deployer
    )
    pool.set_staking(alice, sender=deployer)
    lp_token.set_minter(pool, sender=deployer)
    for token in tokens:
        token.mint(alice, UNIT, sender=alice)
        token.approve(pool, UNIT, sender=alice)
    pool.add_liquidity([UNIT for _ in tokens], 0, sender=alice)
    pool.set_management(proxy, sender=deployer)
    executor.execute_single(pool, pool.accept_management.encode_input(), sender=deployer)
    executor.set_governor(deployer, False, sender=deployer)
    return pool

@pytest.fixture
def wvoting(project, deployer, measure, ivoting, pool):
    return project.WeightVote.deploy(ivoting.genesis(), pool, measure, sender=deployer)

@pytest.fixture
def governor(project, deployer, executor, ivoting, pool, wvoting):
    governor = project.PoolGovernor.deploy(ivoting.genesis(), pool, executor, sender=deployer)
    governor.set_inclusion_vote(ivoting, sender=deployer)
    governor.set_weight_vote(wvoting, sender=deployer)
    assert governor.target_amplification() == 450 * UNIT
    governor.set_target_amplification(500 * UNIT, sender=deployer)
    executor.set_governor(governor, True, sender=deployer)
    return governor

def test_weight_redistribute(chain, deployer, alice, measure, pool, ivoting, wvoting, governor):
    chain.pending_timestamp += VOTE_START
    measure.set_vote_weight(alice, UNIT, sender=alice)
    wvoting.vote([0, 2000, 8000], sender=alice)
    chain.pending_timestamp += WEEK
    ivoting.finalize_epoch(sender=alice)
    governor.execute(0, UNIT//100, 0, 450 * UNIT, 0, sender=deployer)
    assert pool.weight(0)[1] == UNIT * 47 // 100
    assert pool.weight(1)[1] == UNIT * 53 // 100

def test_weight_redistribute_blank(chain, deployer, alice, measure, pool, ivoting, wvoting, governor):
    chain.pending_timestamp += VOTE_START
    measure.set_vote_weight(alice, UNIT, sender=alice)
    wvoting.vote([4000, 2000, 4000], sender=alice)
    chain.pending_timestamp += WEEK
    ivoting.finalize_epoch(sender=alice)
    governor.execute(0, UNIT//100, 0, 450 * UNIT, 0, sender=deployer)
    assert pool.weight(0)[1] == UNIT * 49 // 100
    assert pool.weight(1)[1] == UNIT * 51 // 100

def test_weight_redistribute_full_blank(chain, deployer, alice, measure, pool, ivoting, wvoting, governor):
    chain.pending_timestamp += VOTE_START
    measure.set_vote_weight(alice, UNIT, sender=alice)
    wvoting.vote([10000], sender=alice)
    chain.pending_timestamp += WEEK
    ivoting.finalize_epoch(sender=alice)
    governor.execute(0, UNIT//100, 0, 450 * UNIT, 0, sender=deployer)
    assert pool.weight(0)[1] == UNIT // 2
    assert pool.weight(1)[1] == UNIT // 2

def test_inclusion(chain, deployer, alice, proxy, measure, lp_token, candidate, provider, pool, ivoting, governor):
    provider.set_rate(candidate, UNIT, sender=deployer)
    ivoting.set_rate_provider(candidate, provider, sender=deployer)
    ivoting.apply(candidate, sender=alice)
    chain.pending_timestamp += VOTE_START
    measure.set_vote_weight(alice, UNIT, sender=alice)
    ivoting.vote([0, 10000], sender=alice)
    candidate.mint(proxy, UNIT, sender=alice)
    chain.pending_timestamp += WEEK
    ivoting.finalize_epoch(sender=alice)
    
    n = pool.num_assets()
    assert lp_token.balanceOf(deployer) == 0
    governor.execute(UNIT, UNIT, UNIT//100, 450 * UNIT, 0, sender=deployer)
    assert pool.num_assets() == n + 1
    assert pool.assets(n) == candidate.address
    assert lp_token.balanceOf(deployer) > 0
    assert candidate.balanceOf(pool) == UNIT // 100

    # current weights
    assert pool.weight(0)[0] == UNIT * 49995 // 100000
    assert pool.weight(1)[0] == UNIT * 49995 // 100000
    assert pool.weight(2)[0] == UNIT *    10 // 100000

    # target weights
    assert pool.weight(0)[1] == UNIT * 495 // 1000
    assert pool.weight(1)[1] == UNIT * 495 // 1000
    assert pool.weight(2)[1] == UNIT *  10 // 1000

def test_inclusion_redistribute(chain, deployer, alice, proxy, measure, candidate, provider, pool, ivoting, wvoting, governor):
    governor.set_redistribute_weight(UNIT * 9 // 100, sender=deployer) # make math easier
    provider.set_rate(candidate, UNIT, sender=deployer)
    ivoting.set_rate_provider(candidate, provider, sender=deployer)
    ivoting.apply(candidate, sender=alice)
    chain.pending_timestamp += VOTE_START
    measure.set_vote_weight(alice, UNIT, sender=alice)
    ivoting.vote([0, 10000], sender=alice)
    wvoting.vote([0, 0, 10000], sender=alice)
    candidate.mint(proxy, UNIT, sender=alice)
    chain.pending_timestamp += WEEK
    ivoting.finalize_epoch(sender=alice)
    governor.execute(UNIT, UNIT, UNIT//100, 450 * UNIT, 0, sender=deployer)

    # current weights
    assert pool.weight(0)[0] == UNIT * 49995 // 100000
    assert pool.weight(1)[0] == UNIT * 49995 // 100000
    assert pool.weight(2)[0] == UNIT *    10 // 100000

    # target weights
    assert pool.weight(0)[1] == UNIT * 45 // 100
    assert pool.weight(1)[1] == UNIT * 54 // 100
    assert pool.weight(2)[1] == UNIT *  1 // 100
