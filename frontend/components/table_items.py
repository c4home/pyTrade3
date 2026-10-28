from PyQt6.QtWidgets import QTableWidgetItem


class NumericTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem with custom sorting support via sort_value."""

    def __init__(self, text: str, sort_value):
        super().__init__(text)
        self.sort_value = sort_value

    def __lt__(self, other):
        if hasattr(other, "sort_value"):
            return bool(self.sort_value < other.sort_value)
        return super().__lt__(other)

