# @version 0.3.7

interface Pool:
    def num_assets() -> uint256: view
implements: Pool

num_assets: public(uint256)

@external
def set_num_assets(_num_assets: uint256):
    self.num_assets = _num_assets
