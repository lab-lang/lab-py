"""Experiment families built on the protocol operations.

A family is a package of ordinary functions. Each stage lays out wells, then
appends steps to a caller-owned protocol. Cloning is :mod:`lab.experiments.cloning`.
Add another kind of experiment as a sibling package, and add another stage of
cloning as a module in :mod:`lab.experiments.cloning.stages`. Stages are not registered.
"""
