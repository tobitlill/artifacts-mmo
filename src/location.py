class Location:
    def __init__(self, x: int = 0, y: int = 0):
        self.x: int = x
        self.y: int = y

    def __repr__(self):
        return (self.x, self.y)
