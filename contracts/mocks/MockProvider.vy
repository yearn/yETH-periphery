# @version 0.3.10

interface RateProvider:
    def rate(_asset: address) -> uint256: view
implements: RateProvider

rate: public(HashMap[address, uint256])

@external
def set_rate(_asset: address, _rate: uint256):
    self.rate[_asset] = _rate
