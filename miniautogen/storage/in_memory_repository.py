from miniautogen.stores.in_memory import InMemoryMessageStore


class InMemoryChatRepository(InMemoryMessageStore):
    """Legacy in-memory chat repository kept as a compatibility facade."""
