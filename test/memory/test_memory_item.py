
from backend.src.memory.interfaces.memory_item import MemoryItem

memory_item = MemoryItem(id=1, type="session", data={"user": "liuyikun"})
print(memory_item)
print(memory_item.from_dict({
    "id": 1,
    "type": "session",
    "data": {"user": "liuyikun"},
    "metadata": {"username": "lyk"},
    "created_at": "2026-05-02 00:00:00",
    "updated_at": "2026-05-02 00:00:00",
    "embedding": None
}))

