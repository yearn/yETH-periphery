# @version 0.3.7

interface EtherFiLiquidityPool:
    def amountForShare(_shares: uint256) -> uint256: view

ASSET: constant(address) = 0xCd5fE23C85820F7B72D0926FC9b05b43E359b7ee # weETH
LIQUIDITY_POOL: constant(address) = 0x308861A430be4cce5502d0A12724771Fc6DaF216
UNIT: constant(uint256) = 1_000_000_000_000_000_000

@external
@view
def rate(_asset: address) -> uint256:
    assert _asset == ASSET
    return EtherFiLiquidityPool(LIQUIDITY_POOL).amountForShare(UNIT)
