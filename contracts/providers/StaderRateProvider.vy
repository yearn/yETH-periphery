# @version 0.3.7

struct StaderExchangeRate:
    block_number: uint256
    eth_balance: uint256
    ethx_supply: uint256

interface StaderOracle:
    def getExchangeRate() -> StaderExchangeRate: view

ASSET: constant(address) = 0xA35b1B31Ce002FBF2058D22F30f95D405200A15b # ETHx
ORACLE: constant(address) = 0xF64bAe65f6f2a5277571143A24FaaFDFC0C2a737
UNIT: constant(uint256) = 1_000_000_000_000_000_000

@external
@view
def rate(_asset: address) -> uint256:
    assert _asset == ASSET
    res: StaderExchangeRate = StaderOracle(ORACLE).getExchangeRate()
    return res.eth_balance * UNIT / res.ethx_supply
