"""
gen_perf_circuit.py
===================
Generates a high-throughput benchmark circuit as a flat .json file.

Topology (total ~32K–50K gate evals per toggle):
─────────────────────────────────────────────────
  1. BINARY FANOUT TREE   (depth D, 2^D − 1 AND gates)
     One Variable fans out through D layers, each gate driving two children.
     A constant-HIGH variable feeds the second input of every AND.
     Toggling the root variable cascades through all 2^D − 1 gates.

  2. XOR REDUCTION TREE   (~N−1 gates, N = 2^D leaves)
     All leaf outputs are XOR-reduced pairwise up a balanced binary tree,
     producing a single output bit.  Every toggle of the root propagates
     through the full fanout AND tree then through the full reduction tree.

Total gates triggered per toggle ≈ (2^D − 1) + (2^D − 1) = 2*(2^D − 1)

With D = 14 → 2*(16384 − 1) = 32 766 evals per toggle.
With D = 15 → 2*(32768 − 1) = 65 534   (may exceed 50 K budget).

Adjust DEPTH below to taste.
"""

import orjson
import sys
import os

# ── Configuration ───────────────────────────────────────────────────────────
DEPTH      = 14          # fanout tree depth  (14 → ~32 K, 15 → ~65 K evals)
OUT_FILE   = "heavy_perf.json"
# ────────────────────────────────────────────────────────────────────────────

# Gate type IDs (must match Const.py)
AND_ID      = 0
OR_ID       = 2
XOR_ID      = 4
VARIABLE_ID = 6
NOT_ID      = 7

# Serialisation field offsets
CUSTOM_NAME = 0   # index 0
CODE        = 1   # index 1
INPUTLIMIT  = 2   # index 2
SOURCES     = 3   # index 3  (gates)
VALUE       = 3   # index 3  (variables)

NULL_SRC = ["X", "X"]


class Node:
    """Lightweight stand-in for a Gate — holds just enough to build JSON."""
    __slots__ = ('type_id', 'rank', 'inputlimit', 'sources', 'value')

    def __init__(self, type_id, rank, inputlimit=2, sources=None, value=None):
        self.type_id   = type_id
        self.rank      = rank
        self.inputlimit = inputlimit
        self.sources    = sources or []   # list of [type_id, rank]
        self.value      = value           # only for VARIABLE_ID

    @property
    def code(self):
        return [self.type_id, self.rank]

    def serialise(self):
        if self.type_id == VARIABLE_ID:
            return ["", self.code, self.inputlimit, self.value]
        else:
            return ["", self.code, self.inputlimit, self.sources]


class CircuitBuilder:
    def __init__(self):
        # counters per type_id
        self._ranks = {}
        self._nodes = []   # ordered list — determines load order

    def _next_rank(self, type_id):
        r = self._ranks.get(type_id, 0)
        self._ranks[type_id] = r + 1
        return r

    def add_variable(self, value=0):
        rank = self._next_rank(VARIABLE_ID)
        n = Node(VARIABLE_ID, rank, inputlimit=1, value=value)
        self._nodes.append(n)
        return n

    def add_gate(self, type_id, *sources):
        """
        sources: Node objects to wire as inputs (in order).
        The gate's inputlimit = len(sources).
        """
        rank = self._next_rank(type_id)
        inputlimit = max(2, len(sources))
        src_refs = [s.code for s in sources]
        # pad to inputlimit if needed
        while len(src_refs) < inputlimit:
            src_refs.append(NULL_SRC)
        n = Node(type_id, rank, inputlimit=inputlimit, sources=src_refs)
        self._nodes.append(n)
        return n

    def serialise(self):
        return [n.serialise() for n in self._nodes]


def build_fanout_tree(cb: CircuitBuilder, root: Node, const_hi: Node, depth: int):
    """
    Recursively build a binary AND-gate fanout tree.
    root  → one input of each AND in layer 1
    const_hi → second input of every AND (keeps output stable at root value)
    Returns the list of leaf nodes at the bottom layer.
    """
    layer = [root]
    for _ in range(depth):
        next_layer = []
        for parent in layer:
            left  = cb.add_gate(AND_ID, parent, const_hi)
            right = cb.add_gate(AND_ID, parent, const_hi)
            next_layer.extend([left, right])
        layer = next_layer
    return layer   # 2^depth leaves


def build_xor_tree(cb: CircuitBuilder, leaves: list):
    """
    Pairwise XOR reduction tree. Returns the single root XOR node.
    """
    layer = leaves
    while len(layer) > 1:
        next_layer = []
        for i in range(0, len(layer) - 1, 2):
            xg = cb.add_gate(XOR_ID, layer[i], layer[i + 1])
            next_layer.append(xg)
        if len(layer) % 2 == 1:          # odd one out — pass through via NOT+NOT
            passthru = cb.add_gate(XOR_ID, layer[-1], layer[-1])  # self-XOR = 0 (filler)
            # actually just keep it directly — append it to next_layer so it's
            # consumed in the following round
            next_layer.append(layer[-1])
        layer = next_layer
    return layer[0]


def main():
    print(f"Building circuit  (fanout depth={DEPTH})")
    n_fanout_leaves = 2 ** DEPTH
    n_fanout_gates  = n_fanout_leaves - 1          # internal AND nodes
    n_xor_gates     = n_fanout_leaves - 1          # XOR reduction (balanced binary tree)
    total_gates     = n_fanout_gates + n_xor_gates
    evals_per_toggle = 2 * n_fanout_gates + n_xor_gates
    print(f"  Fanout tree :  {n_fanout_gates:>7,} AND gates  ({n_fanout_leaves:,} leaves)")
    print(f"  XOR reduction: {n_xor_gates:>7,} XOR gates")
    print(f"  ─────────────────────────────────")
    print(f"  Total gates:   {total_gates:>7,}")
    print(f"  Evals/toggle:  ~{evals_per_toggle:>6,}  (upper bound)")

    cb = CircuitBuilder()

    # Two variables: the trigger and a permanently-HIGH rail
    trigger  = cb.add_variable(value=0)
    const_hi = cb.add_variable(value=1)

    print(f"  Building fanout tree...")
    leaves = build_fanout_tree(cb, trigger, const_hi, DEPTH)

    print(f"  Building XOR reduction tree...")
    output  = build_xor_tree(cb, leaves)

    # Serialise
    print(f"  Serialising to JSON...")
    circuit = cb.serialise()

    out_path = os.path.join(os.path.dirname(__file__), OUT_FILE)
    with open(out_path, 'wb') as f:
        f.write(orjson.dumps(circuit))

    size_kb = os.path.getsize(out_path) / 1024
    print(f"\n[OK] Written: {out_path}")
    print(f"     File size: {size_kb:.1f} KB")
    print(f"     Gate count in file: {len(circuit):,}")
    print(f"\nLoad in CLI:  load {out_path}")
    print(f"Then toggle the first variable to trigger the cascade.\n")


if __name__ == "__main__":
    main()
