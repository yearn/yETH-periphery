# @version 0.3.10

interface Pool:
    def num_assets() -> uint256: view
    def killed() -> bool: view
implements: Pool

num_assets: public(uint256)
killed: public(bool)

@external
def set_num_assets(_num_assets: uint256):
    self.num_assets = _num_assets

@external
def set_killed(_killed: bool):
    self.killed = _killed
