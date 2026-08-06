class Location:
    def __init__(self, x: int = 0, y: int = 0):
        self.x: int = x
        self.y: int = y

    def __repr__(self):
        return (self.x, self.y)

    def __eq__(self, other):
        if not isinstance(other, Location):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __ne__(self, other):
            if not isinstance(other, Location):
                return NotImplemented
            return self.x != other.x or self.y != other.y
