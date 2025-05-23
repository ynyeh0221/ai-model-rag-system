import shutil
import tempfile
import unittest
from unittest.mock import patch

from src.core.vector_db.chroma_manager import ChromaManager


# --- Dummy Classes for Testing ---

class DummyEmbeddingFunction:
    def __init__(self, model_name):
        self.model_name = model_name

    def __call__(self, texts):
        # For simplicity, for each input text return a fixed-dimension vector, here of length 5.
        # (In a real case, the embedding would be a numpy array or a list; here we use a list.)
        return [ [1.0] * 5 for _ in texts ]

class DummyCollection:
    def __init__(self, name, embedding_function, metadata=None):
        self.name = name
        self.embedding_function = embedding_function
        self.metadata = metadata or {}
        self.docs = {}  # Store documents as a dict keyed by doc id

    def upsert(self, ids, documents, embeddings, metadatas):
        # Simulate adding documents.
        for i, doc_id in enumerate(ids):
            self.docs[doc_id] = {
                "content": documents[i] if documents else "",
                "metadata": metadatas[i] if metadatas else {},
                "embedding": embeddings[i] if embeddings else None
            }

    def update(self, **update_args):
        ids = update_args.get("ids", [])
        for idx, doc_id in enumerate(ids):
            if doc_id in self.docs:
                if "documents" in update_args and update_args["documents"]:
                    self.docs[doc_id]["content"] = update_args["documents"][idx]
                if "metadatas" in update_args and update_args["metadatas"]:
                    self.docs[doc_id]["metadata"] = update_args["metadatas"][idx]
                if "embeddings" in update_args and update_args["embeddings"]:
                    self.docs[doc_id]["embedding"] = update_args["embeddings"][idx]

    def delete(self, ids):
        for doc_id in ids:
            self.docs.pop(doc_id, None)

    def get(self, ids=None, where=None, limit=None, offset=None, include=None):
        # For simplicity, ignore filtering.
        docs_list = list(self.docs.items())
        # Build nested lists matching the format expected by _process_search_results.
        # In this example, we return a single list wrapped in another list.
        if ids is not None:
            docs_list = [(doc_id, self.docs[doc_id]) for doc_id in ids if doc_id in self.docs]
        ids_list = [ [doc_id for (doc_id, _) in docs_list] ]
        documents_list = [ [doc["content"] for (_, doc) in docs_list] ]
        metadatas_list = [ [doc["metadata"] for (_, doc) in docs_list] ]
        embeddings_list = [ [doc.get("embedding") for (_, doc) in docs_list] ]
        return {
            "ids": ids_list,
            "documents": documents_list,
            "metadatas": metadatas_list,
            "embeddings": embeddings_list
        }

    def query(self, query_embeddings, n_results, include, where=None):
        # For simplicity, use get() and simulate distances as zeros.
        result = self.get()
        # Create a distances array with zeros; same shape as ids list.
        result["distances"] = [ [0.0 for _ in result["ids"][0]] ] if result["ids"][0] else [[]]
        return result

    def count(self):
        return len(self.docs)

class DummyPersistentClient:
    def __init__(self, path, settings):
        self.path = path
        self.settings = settings
        self.collections = {}

    def get_collection(self, name, embedding_function):
        if name in self.collections:
            return self.collections[name]
        else:
            raise ValueError("Collection does not exist")

    def create_collection(self, name, embedding_function, metadata):
        collection = DummyCollection(name, embedding_function, metadata)
        self.collections[name] = collection
        return collection

# --- Unit Test Class ---

class TestChromaManager(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Create a temporary directory for the persistent directory
        self.temp_dir = tempfile.mkdtemp()

        # Patch os.makedirs to avoid issues when creating directories
        self.makedirs_patcher = patch("src.core.vector_db.chroma_manager.os.makedirs")
        self.mock_makedirs = self.makedirs_patcher.start()

        # Patch chromadb.PersistentClient to use our DummyPersistentClient.
        self.client_patcher = patch(
            "src.core.vector_db.chroma_manager.chromadb.PersistentClient",
            side_effect=lambda path, settings: DummyPersistentClient(path, settings)
        )
        self.mock_client = self.client_patcher.start()
        self.text_embedder = DummyEmbeddingFunction("dummy-text")
        self.image_embedder = DummyEmbeddingFunction("dummy-image")

        # Instantiate the ChromaManager with our temporary directory.
        self.manager = ChromaManager(
            text_embedder=self.text_embedder,
            image_embedder=self.image_embedder,
            persist_directory=self.temp_dir
        )
        # Override _run_in_executor so that functions run synchronously.
        async def immediate(func, *args, **kwargs):
            return func(*args, **kwargs)
        self.manager._run_in_executor = immediate

    def tearDown(self):
        self.makedirs_patcher.stop()
        self.client_patcher.stop()
        # Clean up temporary directory if needed.
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_initialize_default_collections(self):
        # Updated to match actual collection names initialized in ChromaManager
        expected_collections = {
            "model_scripts_metadata",
            "model_scripts_chunks",
            "generated_images"
        }
        actual_collections = set(self.manager.collections.keys())

        self.assertTrue(
            expected_collections.issubset(actual_collections),
            msg=f"Expected collections {expected_collections} not found in actual collections {actual_collections}"
        )

        # Also ensure that the dummy client has these collections
        for name in expected_collections:
            collection = self.manager.collections.get(name)
            self.assertIsNotNone(collection, f"Collection '{name}' not found in manager")
            self.assertIsInstance(collection, DummyCollection)

    async def test_get_collection_creates_new(self):
        # Request a collection that does not exist in the cache.
        new_name = "custom_collection"
        collection = self.manager.get_collection(new_name)
        self.assertIsInstance(collection, DummyCollection)
        self.assertEqual(collection.name, new_name)
        # Now it should be cached.
        self.assertEqual(self.manager.collections[new_name], collection)

    async def test_add_document(self):
        # Test adding a single document to the "model_script_processing" collection.
        document = {
            "id": "doc1",
            "content": "print('Hello World')",
            "metadata": {"model_id": "123", "version": "1.0"}
        }
        doc_id = await self.manager.add_document(document, collection_name="model_script_processing")
        self.assertEqual(doc_id, "doc1")
        # Check that the document exists in the dummy collection.
        collection = self.manager.get_collection("model_script_processing")
        self.assertTrue(
            document["metadata"].items() <= collection.docs["doc1"]["metadata"].items()
        )

    async def test_add_documents(self):
        # Test batch addition of documents.
        documents = [
            {"id": "doc1", "content": "Content 1", "metadata": {"info": "A"}},
            {"id": "doc2", "content": "Content 2", "metadata": {"info": "B"}}
        ]
        ids = await self.manager.add_documents(documents, collection_name="model_script_processing")
        self.assertCountEqual(ids, ["doc1", "doc2"])
        collection = self.manager.get_collection("model_script_processing")
        for doc_id in ids:
            self.assertIn(doc_id, collection.docs)

    async def test_search_text_query(self):
        # Seed a document and then perform a search.
        document = {
            "id": "doc_search",
            "content": "Find me",
            "metadata": {"model_id": "456"}
        }
        await self.manager.add_document(document, collection_name="model_script_processing")
        # Search using a text query.
        results = await self.manager.search("Find me", collection_name="model_script_processing")
        # Processed search results returns a dictionary with key "results".
        self.assertIn("results", results)
        # At least one result should be returned.
        self.assertGreaterEqual(len(results["results"]), 1)
        # Check that the returned document id is "doc_search".
        self.assertEqual(results["results"][0]["id"], "doc_search")

    async def test_get_documents(self):
        # Add two documents.
        documents = [
            {"id": "doc_get1", "content": "Content 1", "metadata": {"a": 1}},
            {"id": "doc_get2", "content": "Content 2", "metadata": {"a": 2}}
        ]
        await self.manager.add_documents(documents, collection_name="model_script_processing")
        # Retrieve documents by ids.
        results = await self.manager.get(collection_name="model_script_processing", ids=["doc_get1", "doc_get2"])
        self.assertIn("results", results)
        returned_ids = [doc["id"] for doc in results["results"]]
        self.assertCountEqual(returned_ids, ["doc_get1", "doc_get2"])

    async def test_get_document(self):
        # Add a document and then retrieve it by doc_id.
        document = {
            "id": "single_doc",
            "content": "Unique Content",
            "metadata": {"info": "unique"}
        }
        await self.manager.add_document(document, collection_name="model_script_processing")
        doc = await self.manager.get_document("single_doc", collection_name="model_script_processing")
        self.assertIsNotNone(doc)
        self.assertEqual(doc["id"], "single_doc")
        self.assertEqual(doc["document"], "Unique Content")

    async def test_update_document(self):
        # Add a document then update its content.
        document = {
            "id": "doc_update",
            "content": "Old Content",
            "metadata": {"version": "1.0"}
        }
        await self.manager.add_document(document, collection_name="model_script_processing")
        update_data = {
            "content": "New Content",
            "metadata": {"version": "2.0"}
        }
        success = await self.manager.update_document("doc_update", update_data, collection_name="model_script_processing")
        self.assertTrue(success)
        # Verify update.
        doc = await self.manager.get_document("doc_update", collection_name="model_script_processing")
        self.assertEqual(doc["document"], "New Content")
        self.assertEqual(doc["metadata"], {"version": "2.0"})

    async def test_delete_document(self):
        # Add a document then delete it.
        document = {
            "id": "doc_delete",
            "content": "To be deleted",
            "metadata": {}
        }
        await self.manager.add_document(document, collection_name="model_script_processing")
        success = await self.manager.delete_document("doc_delete", collection_name="model_script_processing")
        self.assertTrue(success)
        # Verify deletion.
        doc = await self.manager.get_document("doc_delete", collection_name="model_script_processing")
        self.assertIsNone(doc)

    async def test_delete_documents(self):
        # Add multiple documents.
        documents = [
            {"id": "doc_d1", "content": "A", "metadata": {"test": "value1"}},
            {"id": "doc_d2", "content": "B", "metadata": {"test": "value2"}}
        ]
        await self.manager.add_documents(documents, collection_name="model_script_processing")
        # Delete documents matching a filter.
        # Note: In our dummy implementation, the where filter doesn't actually filter,
        # but we're testing the API calls correctly flow through.
        deleted_count = await self.manager.delete_documents(where={"test": {"$eq": "value1"}}, collection_name="model_script_processing")
        # Verify the count is as expected
        self.assertEqual(deleted_count, 2)  # Our dummy implementation returns all docs
        # Verify that the collection is now empty.
        count = await self.manager.count_documents(collection_name="model_script_processing")
        self.assertEqual(count, 0)

    async def test_count_documents(self):
        # Add documents and then count.
        documents = [
            {"id": "doc_c1", "content": "Content", "metadata": {}},
            {"id": "doc_c2", "content": "Content", "metadata": {}}
        ]
        await self.manager.add_documents(documents, collection_name="model_script_processing")
        count = await self.manager.count_documents(collection_name="model_script_processing")
        self.assertEqual(count, 2)

    async def test_apply_access_control(self):
        # Test that _apply_access_control returns the expected filter structure.
        where = {"metadata.key": "value"}
        user_id = "user123"
        controlled = self.manager._apply_access_control(where, user_id)
        # The result should be a dict with "$and" key containing the original where clause and the access filter.
        self.assertIn("$and", controlled)
        self.assertEqual(controlled["$and"][0], where)
        # Check that the access filter contains conditions for the given user_id.
        access_filter = controlled["$and"][1]
        self.assertIn("$or", access_filter)
        self.assertEqual(access_filter["$or"][0]["access_control.owner"]["$eq"], user_id)

if __name__ == "__main__":
    unittest.main()
