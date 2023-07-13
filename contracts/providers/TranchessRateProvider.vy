# @version 0.3.7

interface TranchessFund:
    def getTotalUnderlying() -> uint256: view
    def getEquivalentTotalQ() -> uint256: view

ASSET: constant(address) = 0x93ef1Ea305D11A9b2a3EbB9bB4FCc34695292E7d # qETH
FUND: constant(address) = 0x69c53679EC1C06f3275b64C428e8Cd069a2d3966
UNIT: constant(uint256) = 1_000_000_000_000_000_000

@external
@view
def rate(_asset: address) -> uint256:
    assert _asset == ASSET
    return TranchessFund(FUND).getTotalUnderlying() * UNIT / TranchessFund(FUND).getEquivalentTotalQ()
