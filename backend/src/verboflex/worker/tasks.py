"""Callable task seams implemented through strict TDD."""


class _AddTaskSeam:
    """Final named-task shape before its first behavior is implemented."""

    name = "verboflex.add"

    def run(self, _left: int, _right: int) -> int:
        """Keep the pure task path callable for a meaningful RED."""
        raise NotImplementedError("sample add task is not implemented")


add = _AddTaskSeam()
