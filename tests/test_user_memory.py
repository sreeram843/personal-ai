from app.services.user_memory import UserMemoryStore


def test_user_memory_store_records_and_blocks(tmp_path):
    store = UserMemoryStore(file_path=str(tmp_path / "user_memory.json"), max_entries_per_user=3)
    store.record_turn("user-1", user_message="What is RAG?", assistant_message="Retrieval augmented generation combines search with LLM answers.")
    store.record_turn("user-1", user_message="Thanks", assistant_message="You're welcome.")

    block = store.get_memory_block("user-1")
    assert "User memory" in block
    assert "What is RAG?" in block
    assert "You're welcome" in block

    store.record_turn("user-1", user_message="Third", assistant_message="Third reply")
    store.record_turn("user-1", user_message="Fourth", assistant_message="Fourth reply")
    block_after_trim = store.get_memory_block("user-1", limit=10)
    assert "What is RAG?" not in block_after_trim
    assert "Fourth" in block_after_trim
