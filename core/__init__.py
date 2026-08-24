"""Pure product logic for the A-line workflow.

Nothing in this package performs I/O: the state machine, guards, and the
classification chain are pure functions over models from `schemas/`, so both
`api/` and `workers/` can import them and unit tests need no emulators.
"""
