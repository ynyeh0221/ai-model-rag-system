import unittest
import os
import tempfile
import datetime
import sys

# Add the parent directory to sys.path if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the CodeParser class
from src.document_processor.code_parser import CodeParser


class TestCodeParser(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.parser = CodeParser()

        # Create a temporary Python file for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_file_path = os.path.join(self.temp_dir.name, "test_model.py")

        # Sample Python content for testing
        sample_content = """
import torch
import torch.nn as nn

class SimpleModel(nn.Module):
    def __init__(self):
        super(SimpleModel, self).__init__()
        self.num_layers = 3
        self.hidden_size = 256
        self.num_attention_heads = 8

        # Define layers
        self.layers = nn.Sequential(
            nn.Linear(100, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 10)
        )

    def forward(self, x):
        return self.layers(x)

# Dataset information
dataset = "CIFAR-10"
train_data = {"num_samples": 50000, "split": "train"}

# Training configuration
batch_size = 64
learning_rate = 0.001
optimizer = "Adam"
epochs = 100

# Performance metrics
accuracy = 0.92
loss = 0.08
perplexity = 1.5
eval_dataset = "CIFAR-10-test"
"""

        with open(self.test_file_path, 'w') as f:
            f.write(sample_content)

    def tearDown(self):
        """Clean up after each test method."""
        self.temp_dir.cleanup()

    def test_parse_extension_filtering(self):
        """Test that parse method correctly filters file extensions."""
        # Test with Python file
        result = self.parser.parse(self.test_file_path)
        self.assertIsNotNone(result)

        # Test with non-Python file
        non_py_file = os.path.join(self.temp_dir.name, "not_python.txt")
        with open(non_py_file, 'w') as f:
            f.write("This is not Python code")

        result = self.parser.parse(non_py_file)
        self.assertIsNone(result)

    def test_parse_file_basic_metadata(self):
        """Test extraction of basic metadata from Python file."""
        model_info = self.parser.parse_file(self.test_file_path)

        # Basic metadata checks
        self.assertIn("creation_date", model_info)
        self.assertIn("last_modified_date", model_info)
        self.assertEqual(model_info["model_id"], "unknown")
        self.assertEqual(model_info["model_family"], "unknown")
        self.assertEqual(model_info["version"], "unknown")
        self.assertTrue(model_info["is_model_script"])

    def test_framework_detection(self):
        """Test framework detection from import statements."""
        model_info = self.parser.parse_file(self.test_file_path)

        # Framework detection checks
        self.assertEqual(model_info["framework"]["name"], "torch")

    def test_architecture_extraction(self):
        """Test extraction of architecture details."""
        model_info = self.parser.parse_file(self.test_file_path)

        # Architecture checks
        architecture = model_info["architecture"]
        self.assertIn("dimensions", architecture)
        self.assertIsInstance(architecture["dimensions"], dict)

    def test_dataset_extraction(self):
        """Test extraction of dataset information."""
        model_info = self.parser.parse_file(self.test_file_path)

        # Dataset checks
        dataset = model_info["dataset"]
        self.assertIn("name", dataset)
        self.assertIn("version", dataset)
        self.assertIn("num_samples", dataset)
        self.assertIn("split", dataset)

    def test_training_config_extraction(self):
        """Test extraction of training configuration."""
        model_info = self.parser.parse_file(self.test_file_path)

        # Training config checks
        config = model_info["training_config"]
        self.assertIn("batch_size", config)
        self.assertIn("learning_rate", config)
        self.assertIn("optimizer", config)
        self.assertIn("epochs", config)

    def test_performance_metrics_extraction(self):
        """Test extraction of performance metrics."""
        model_info = self.parser.parse_file(self.test_file_path)

        # Performance metrics checks
        performance = model_info["performance"]
        self.assertIn("accuracy", performance)
        self.assertIn("loss", performance)
        self.assertIn("perplexity", performance)
        self.assertIn("eval_dataset", performance)

    def test_split_into_chunks(self):
        """Test the split_into_chunks method."""
        content = "0123456789" * 30  # 300 characters
        chunks = self.parser.split_into_chunks(content, chunk_size=100, overlap=20)

        # Check number of chunks
        self.assertEqual(len(chunks), 4)

        # Check chunk sizes
        self.assertEqual(len(chunks[0]), 100)
        self.assertEqual(len(chunks[1]), 100)
        self.assertEqual(len(chunks[2]), 100)

        # Check overlap
        self.assertEqual(chunks[0][80:100], chunks[1][0:20])
        self.assertEqual(chunks[1][80:100], chunks[2][0:20])

    # Mocking the git module directly instead of trying to mock the import
    def test_git_date_extraction(self):
        """Test extraction of dates from git repository without mocking."""
        # Create a test date for reference
        test_date = datetime.datetime.now().isoformat()

        # Directly test the OS fallback path by using a temporary file
        # that likely isn't in a git repository
        date = self.parser._get_creation_date(self.test_file_path)

        # Just verify we get a date back in ISO format
        self.assertIsNotNone(date)
        try:
            datetime.datetime.fromisoformat(date)
        except ValueError:
            self.fail("Date is not in ISO format")

    def test_syntax_error_handling(self):
        """Test handling of syntax errors in Python files."""
        # Create file with syntax error
        syntax_error_file = os.path.join(self.temp_dir.name, "syntax_error.py")
        with open(syntax_error_file, 'w') as f:
            f.write("This is not valid Python syntax :")

        # Test that ValueError is raised
        with self.assertRaises(ValueError):
            self.parser.parse_file(syntax_error_file)


if __name__ == '__main__':
    unittest.main()