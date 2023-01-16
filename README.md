# Valphi Defeasible Reasoner

A system for defeasible reasoning over weighted knowledge bases.


# Prerequisites

- Updated [conda](https://docs.conda.io/en/latest/)


# Install

Create a conda environment by running
```bash
$ ./bin/create-environment.sh
```
It will use the name `valphi` by default, but a different name can be specified when asked.

Activate the conda environment and install dependencies with `poetry`:
```bash
$ conda activate valphi
(valphi) $ poetry install
```
Note that `poetry` is the one in the conda environment, not your local installation of `poetry`.


# Usage

To find all solutions of a multi-layer network, for example the one in `examples/kbmonk1.network`, run
```bash
(valphi) $ ./valphi_cli.py --network-topology examples/kbmonk1.network --weight-constraints --ordered solve
```

To answer a query use
```bash
(valphi) $ ./valphi_cli.py --network-topology examples/kbmonk1.network --weight-constraints --ordered query --query-filename examples/kbmonk1-1.query
```

A description of the available options is given by
```bash
(valphi) $ ./valphi_cli.py --help
(valphi) $ ./valphi_cli.py solve --help
(valphi) $ ./valphi_cli.py query --help
```


# Multi-Layer (Fully-Connected) Network format

The input layer is implicit.
Each one of the other layers is encoded by a sequence of lines terminated by a line containing `#`.
Each line encodes a node of the layer, and consists of a space-separated list of weights.
The first weight is the bias of the node, the other weights are the influence of nodes in the previous layer.

Layers are indexed starting by 1, and can be marked as crisp (binary evaluation) by adding a line
```
crisp INDEX
```

Exactly-one constraints on the nodes of the input layer (layer 1) can be specified by adding lines of the form
```
=1 NODE-INDEX NODE-INDEX ...
```
where each `NODE-INDEX` is the index of a node in the input layer, again indexed starting by 1.


# Graph format

The first line is
```
#graph
```

The other lines have three integers encoding a weighted link of the graph.


# DIMACS format

`valphi` can solve the MAXSAT problem for CNF formulas encoded in the DIMACS format, but don't expect it to be competitive with MAXSAT solvers.
In fact, in this context the solving approach of `valphi` is not optimized, and a simple reduction (or compilation) of the problem is adopted.
