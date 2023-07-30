# @version 0.3.7

interface BinanceToken:
    def exchangeRate() -> uint256: view

ASSET: constant(address) = 0xa2E3356610840701BDf5611a53974510Ae27E2e1 # wBETH
UNIT: constant(uint256) = 1_000_000_000_000_000_000

@external
@view
def rate(_asset: address) -> uint256:
    assert _asset == ASSET
    return BinanceToken(ASSET).exchangeRate()
