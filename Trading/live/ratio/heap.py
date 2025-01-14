import heapq
import json
from pydantic import BaseModel
from typing import Any, Callable, List, Tuple
from pydantic import BaseModel, Field
from Trading.model.trade import TradesAnalysisResult

class Heap(BaseModel):
    max_len: int
    data: List[List] = Field(default_factory=list)

    # This will be called to initialize the class
    def __init__(self, **data):
        super().__init__(**data)
        self._key = lambda x: x[0]  # Default key

    def get_nth_largest(self, n):
        return heapq.nlargest(n, self.data)

    def push(self, item):
        if len(self.data) < self.max_len:
            heapq.heappush(self.data, item)
        else:
            heapq.heappushpop(self.data, item)

    def largest(self):
        return self.get_nth_largest(1)[0]

    def get(self):
        return sorted(self.data, key=self._key)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, i):
        return self.data[i]

    def __iter__(self):
        return iter(self.data)

    def __repr__(self):
        return str(self.data)

    @staticmethod
    def deserialize(data):
        deserialized_data = []
        for entry in data['data']:
            deserialized_data.append([
                entry[0],  # First element (e.g., priority)
                entry[1],  # Second element (e.g., identifier)
                TradesAnalysisResult(**entry[2])  # Convert dict to TradeAnalysisResult
            ])
        data['data'] = deserialized_data
        return Heap(**data)

# h = Heap(max_len=3)
# h.push([1, "a"])
# h.push([2, "b"])
# h.push([3, "c"])

# print(h)
# s=h.model_dump()
# l = Heap(**s)
# print(l)
# l.push([4, "d"])
