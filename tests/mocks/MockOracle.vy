# pragma version ~=0.4.3
"""
@title Mock Price Oracle
@custom:contract-name MockOracle
@license GNU Affero General Public License v3.0 only
@notice Test-only implementation of `IOracle` whose
        answer, timestamp, and decimals are freely
        settable.
"""

decimals: public(uint8)
latest_answer: public(uint256)
latest_timestamp: public(uint256)


@deploy
def __init__(decimals_: uint8, answer: uint256):
    self.decimals = decimals_
    self.latest_answer = answer
    self.latest_timestamp = block.timestamp


@external
def set_answer(answer: uint256):
    # Mirrors a real feed update: a new answer is always fresh.
    self.latest_answer = answer
    self.latest_timestamp = block.timestamp


@external
def set_timestamp(timestamp: uint256):
    self.latest_timestamp = timestamp
