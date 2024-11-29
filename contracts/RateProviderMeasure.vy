# @version 0.3.10

interface RateProvider:
    def rate(_asset: address) -> uint256: view

@external
def rate(_provider: address, _asset: address) -> uint256:
    return RateProvider(_provider).rate(_asset)

@external
def baseline(_provider: address, _asset: address) -> uint256:
    return 0
