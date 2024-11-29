# @version 0.3.10

interface Measure:
    def total_vote_weight() -> uint256: view
    def vote_weight(_account: address) -> uint256: view

implements: Measure

total_vote_weight: public(uint256)
vote_weight: public(HashMap[address, uint256])

@external
def set_vote_weight(_account: address, _weight: uint256):
    self.vote_weight[_account] = _weight
