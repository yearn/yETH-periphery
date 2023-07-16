# @version 0.3.7

struct StaderExchangeRate:
    block_number: uint256
    eth_balance: uint256
    ethx_supply: uint256

interface StaderOracle:
    def getExchangeRate() -> StaderExchangeRate: view

interface StaderManager:
    def staderConfig() -> address: view

interface StaderConfig:
    def getStaderOracle() -> address: view

ASSET: constant(address) = 0xA35b1B31Ce002FBF2058D22F30f95D405200A15b # ETHx
ORACLE: constant(address) = 0xF64bAe65f6f2a5277571143A24FaaFDFC0C2a737
MANAGER: constant(address) = 0xcf5EA1b38380f6aF39068375516Daf40Ed70D299
UNIT: constant(uint256) = 1_000_000_000_000_000_000

@external
@view
def rate(_asset: address) -> uint256:
    assert _asset == ASSET
    res: StaderExchangeRate = StaderOracle(ORACLE).getExchangeRate()
    return res.eth_balance * UNIT / res.ethx_supply

# for testing purposes
@external
def verify_oracle_contract():
    config: address = StaderManager(MANAGER).staderConfig()
    oracle: address = StaderConfig(config).getStaderOracle()
    assert oracle == ORACLE
