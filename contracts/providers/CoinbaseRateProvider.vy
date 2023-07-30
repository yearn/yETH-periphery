# @version 0.3.7

interface CoinbaseToken:
    def exchangeRate() -> uint256: view

ASSET: constant(address) = 0xBe9895146f7AF43049ca1c1AE358B0541Ea49704 # cbETH
UNIT: constant(uint256) = 1_000_000_000_000_000_000

@external
@view
def rate(_asset: address) -> uint256:
    assert _asset == ASSET
    return CoinbaseToken(ASSET).exchangeRate()
