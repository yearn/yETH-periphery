# @version 0.3.7

interface LidoToken:
    def getPooledEthByShares(_shares: uint256) -> uint256: view

ASSET: constant(address) = 0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0 # wstETH
UDERLYING: constant(address) = 0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84 # stETH
UNIT: constant(uint256) = 1_000_000_000_000_000_000

@external
@view
def rate(_asset: address) -> uint256:
    assert _asset == ASSET
    return LidoToken(UDERLYING).getPooledEthByShares(UNIT)
