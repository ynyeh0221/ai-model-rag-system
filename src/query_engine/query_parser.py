# src/query_engine/query_parser.py

import re
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import spacy
from enum import Enum
import logging
from typing import Dict, List, Any, Optional

# Define intent types as an Enum for type safety
class QueryIntent(Enum):
    RETRIEVAL = "retrieval"  # Basic information retrieval
    COMPARISON = "comparison"  # Model comparison
    NOTEBOOK = "notebook"  # Notebook generation
    IMAGE_SEARCH = "image_search"  # Image search/retrieval
    METADATA = "metadata"  # Metadata-specific queries
    UNKNOWN = "unknown"  # Unknown/ambiguous intent

class QueryParser:
    """
    Parser for natural language queries related to AI models.
    Responsible for intent classification and parameter extraction.
    """
    
    def __init__(self, nlp_model: str = "en_core_web_sm", use_langchain: bool = True):
        """
        Initialize the QueryParser with necessary NLP components.
        
        Args:
            nlp_model: The spaCy model to use for NLP tasks
            use_langchain: Whether to use LangChain for enhanced parsing
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize NLP components
        try:
            self.nlp = spacy.load(nlp_model)
            self.logger.info(f"Loaded spaCy model: {nlp_model}")
        except OSError:
            self.logger.warning(f"Could not load spaCy model: {nlp_model}. Running spacy download...")
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", nlp_model], check=True)
            self.nlp = spacy.load(nlp_model)
        
        # Ensure NLTK resources are available
        try:
            nltk.data.find('tokenizers/punkt')
            nltk.data.find('corpora/stopwords')
            nltk.data.find('corpora/wordnet')
        except LookupError:
            self.logger.info("Downloading required NLTK resources...")
            nltk.download('punkt')
            nltk.download('stopwords')
            nltk.download('wordnet')
        
        self.lemmatizer = WordNetLemmatizer()
        self.stop_words = set(stopwords.words('english'))
        
        # Initialize LangChain components if enabled
        self.use_langchain = use_langchain
        if use_langchain:
            try:
                # Adjust this if your version requires a submodule import.
                from langchain_ollama import OllamaLLM
                from langchain.chains import LLMChain
                from langchain.prompts import PromptTemplate

                # Define a prompt template for intent classification
                intent_template = """
                Classify the following query about AI models into one of these categories:
                - retrieval: Basic information retrieval about models
                - comparison: Comparing multiple models
                - notebook: Generating a notebook for model analysis
                - image_search: Searching for images generated by models
                - metadata: Queries about model metadata
                - unknown: Cannot determine the intent

                Query: {query}

                Intent:
                """

                self.intent_prompt = PromptTemplate(
                    input_variables=["query"],
                    template=intent_template
                )

                # Use the correct model identifier as expected by Ollama.
                self.langchain_llm = OllamaLLM(model="llama3:latest", temperature=0)

                self.intent_chain = self.intent_prompt | self.langchain_llm

                # Define a prompt template for parameter extraction
                param_template = """
                Extract parameters from this query about AI models.
                Return a JSON object with these possible keys:
                - model_ids: List of model IDs mentioned
                - metrics: Performance metrics of interest
                - filters: Any filtering criteria
                - limit: Number of results to return
                - sort_by: Sorting criteria
                - timeframe: Any time constraints

                Only include keys that are relevant to the query.

                Query: {query}

                Parameters:
                """

                self.param_prompt = PromptTemplate(
                    input_variables=["query"],
                    template=param_template
                )

                self.param_chain = self.param_prompt | self.langchain_llm

                self.logger.info("LangChain components initialized successfully")
            except Exception as e:
                self.logger.warning(f"LangChain not available: {e}. Falling back to rule-based parsing")
                self.use_langchain = False

        # Initialize pattern dictionaries for rule-based parsing
        self._init_patterns()
    
    def _init_patterns(self):
        """Initialize regex patterns and keywords for rule-based parsing."""
        # Intent classification patterns
        self.intent_patterns = {
            QueryIntent.RETRIEVAL: [
                r"find|get|retrieve|show|display|tell me about|information on|details of",
                r"what (is|are)|how (is|are)|where (is|are)|when (was|were)"
            ],
            QueryIntent.COMPARISON: [
                r"compare|versus|vs\.?|difference between|similarities between|better than",
                r"which (is|are) (better|worse|faster|more accurate)",
                r"(compare|comparing) the (performance|accuracy|results) of"
            ],
            QueryIntent.NOTEBOOK: [
                r"(create|generate|make|build) (a |an )?(notebook|colab|code|script)",
                r"jupyter|analysis script|analysis code",
                r"notebook (for|to) (analyze|explore|compare)"
            ],
            QueryIntent.IMAGE_SEARCH: [
                r"(find|get|retrieve|show|display) (image|picture|photo)",
                r"(generated|created) (by|with|using)",
                r"(show|find|get) (me )?(examples|samples) (of|from)"
            ],
            QueryIntent.METADATA: [
                r"metadata|schema|fields|properties|attributes",
                r"what (fields|properties|attributes) (does|do)",
                r"(structure|organization) of"
            ]
        }
        
        # Parameter extraction patterns
        self.model_id_pattern = r"(model[_-]?id|model)[:\s]+([a-zA-Z0-9_-]+)"
        self.metric_pattern = r"(accuracy|loss|perplexity|clip[_-]?score|performance)"
        self.filter_patterns = {
            "architecture": r"architecture[:\s]+(transformer|cnn|rnn|mlp|diffusion|gan)",
            "framework": r"framework[:\s]+(pytorch|tensorflow|jax)",
            "params": r"(parameters|params)[\s:]+(greater than|less than|equal to|>|<|=)\s*(\d+[KkMmBbTt]?)",
            "date": r"(created|modified|updated)[\s:]+(before|after|between|since)\s+([a-zA-Z0-9_-]+)"
        }
        self.limit_pattern = r"(limit|top|first)\s+(\d+)"
        self.sort_pattern = r"(sort|order)\s+(by|on)\s+([a-zA-Z_]+)\s+(ascending|descending|asc|desc)?"
        
        # Model name detection - common model families
        self.model_families = [
            "transformer", "gpt", "bert", "t5", "llama", "clip", 
            "stable diffusion", "dalle", "cnn", "resnet", "vit", 
            "swin", "yolo", "diffusion", "vae", "gan"
        ]

    def parse_query(self, query_text: str) -> Dict[str, Any]:
        """
        Parse a query to determine intent and parameters.

        Args:
            query_text: The raw query text from the user

        Returns:
            A dictionary containing:
                - intent: The classified intent as a string (not enum)
                - type: Same as intent for backward compatibility
                - parameters: Dictionary of extracted parameters
                - processed_query: The preprocessed query text
        """
        self.logger.debug(f"Parsing query: {query_text}")

        # Preprocess the query
        processed_query = self.preprocess_query(query_text)

        # Classify intent
        intent = self.classify_intent(query_text)

        # Extract parameters
        parameters = self.extract_parameters(query_text, intent)

        # Convert intent enum to string value for serialization
        intent_str = intent.value if hasattr(intent, 'value') else str(intent)

        result = {
            "intent": intent_str,
            "type": intent_str,  # Add type for backward compatibility
            "parameters": parameters,
            "processed_query": processed_query
        }

        self.logger.info(f"Query parsed: {intent_str} with {len(parameters)} parameters")
        self.logger.debug(f"Parsed result: {result}")

        return result
    
    def classify_intent(self, query_text: str) -> QueryIntent:
        """
        Classify the intent of a query.
        
        Args:
            query_text: The query text to classify
            
        Returns:
            QueryIntent: The classified intent
        """
        if self.use_langchain:
            try:
                # Use LangChain for intent classification
                raw_result = self.intent_chain.invoke({"query": query_text}).strip().lower()

                # Use a more robust extraction method
                # Look for specific intent keywords in the response
                intents = [intent.value for intent in QueryIntent]
                result = None

                # First try to find direct mentions with quotes
                # This handles formats like: i would classify this query as "retrieval: basic..."
                import re
                quoted_pattern = re.compile(r'"([^"]*)"')
                quoted_matches = quoted_pattern.findall(raw_result)

                for quoted_text in quoted_matches:
                    # Check if any intent is at the start of the quoted text
                    for intent in intents:
                        if quoted_text.startswith(intent) or quoted_text.startswith(f"{intent}:"):
                            result = intent
                            break
                    if result:
                        break

                # If no match found in quotes, try direct word matching
                if result is None:
                    for intent in intents:
                        if intent in raw_result:
                            result = intent
                            break

                # If still no match, try the original approach as fallback
                if result is None and ":" in raw_result:
                    possible_intent = raw_result.split(":")[0].strip()
                    # Remove any extra text before the intent name
                    for intent in intents:
                        if intent in possible_intent:
                            result = intent
                            break

                # If we found a matching intent, return it
                if result:
                    for intent in QueryIntent:
                        if intent.value == result:
                            return intent

                # Default to RETRIEVAL if no match (safer default than UNKNOWN)
                self.logger.warning(f"LangChain returned unrecognized intent: {raw_result}")
                return QueryIntent.RETRIEVAL  # Change from UNKNOWN to RETRIEVAL

            except Exception as e:
                self.logger.error(f"Error using LangChain for intent classification: {e}")
                # Fall back to rule-based approach
        
        # Rule-based intent classification
        query_lower = query_text.lower()
        
        # Check for multiple model mentions - strong indicator of comparison
        model_mentions = self._extract_model_mentions(query_lower)
        if len(model_mentions) > 1 and any(re.search(pattern, query_lower) for pattern in self.intent_patterns[QueryIntent.COMPARISON]):
            return QueryIntent.COMPARISON
        
        # Check for notebook generation indicators
        if any(re.search(pattern, query_lower) for pattern in self.intent_patterns[QueryIntent.NOTEBOOK]):
            return QueryIntent.NOTEBOOK
        
        # Check for image search indicators
        if any(re.search(pattern, query_lower) for pattern in self.intent_patterns[QueryIntent.IMAGE_SEARCH]):
            return QueryIntent.IMAGE_SEARCH
        
        # Check for metadata query indicators
        if any(re.search(pattern, query_lower) for pattern in self.intent_patterns[QueryIntent.METADATA]):
            return QueryIntent.METADATA
        
        # Default to retrieval for any other query that doesn't match specific patterns
        if any(re.search(pattern, query_lower) for pattern in self.intent_patterns[QueryIntent.RETRIEVAL]) or len(model_mentions) > 0:
            return QueryIntent.RETRIEVAL
        
        # If no clear patterns match, use NLP-based classification
        return self._nlp_based_intent_classification(query_text)
    
    def _nlp_based_intent_classification(self, query_text: str) -> QueryIntent:
        """
        Use NLP techniques to classify intent when rule-based approach is inconclusive.
        
        Args:
            query_text: The query text to classify
            
        Returns:
            QueryIntent: The classified intent
        """
        # Parse with spaCy
        doc = self.nlp(query_text)
        
        # Extract verbs and nouns for intent analysis
        verbs = [token.lemma_ for token in doc if token.pos_ == "VERB"]
        nouns = [token.lemma_ for token in doc if token.pos_ == "NOUN"]
        
        # Check for comparison-related verbs and multiple entity mentions
        comparison_verbs = ["compare", "contrast", "differ", "distinguish", "evaluate"]
        if any(verb in comparison_verbs for verb in verbs) and len(set(nouns)) > 1:
            return QueryIntent.COMPARISON
        
        # Check for notebook-related nouns
        notebook_nouns = ["notebook", "colab", "code", "script", "analysis"]
        if any(noun in notebook_nouns for noun in nouns):
            return QueryIntent.NOTEBOOK
        
        # Check for image-related nouns
        image_nouns = ["image", "picture", "photo", "visualization", "render", "sample"]
        if any(noun in image_nouns for noun in nouns):
            return QueryIntent.IMAGE_SEARCH
        
        # Check for metadata-related nouns
        metadata_nouns = ["metadata", "schema", "field", "property", "attribute", "structure"]
        if any(noun in metadata_nouns for noun in nouns):
            return QueryIntent.METADATA
        
        # Default to retrieval if we've found some model-related terms
        model_nouns = ["model", "transformer", "neural", "network", "ai", "architecture"]
        if any(noun in model_nouns for noun in nouns):
            return QueryIntent.RETRIEVAL
        
        # If still uncertain, default to UNKNOWN
        return QueryIntent.UNKNOWN
    
    def extract_parameters(self, query_text: str, intent: Optional[QueryIntent] = None) -> Dict[str, Any]:
        """
        Extract parameters from a query based on its intent.
        
        Args:
            query_text: The query text to extract parameters from
            intent: The query intent, if already classified
            
        Returns:
            Dictionary of extracted parameters
        """
        if intent is None:
            intent = self.classify_intent(query_text)

        if self.use_langchain:
            try:
                # Use LangChain for parameter extraction
                import json
                import re

                raw_result = self.param_chain.invoke({"query": query_text})

                # Try to extract JSON from markdown code blocks if present
                json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_result)
                if json_match:
                    json_str = json_match.group(1).strip()
                else:
                    # If no code block, use the whole response
                    json_str = raw_result.strip()

                try:
                    # Parse the JSON result
                    params = json.loads(json_str)
                    return params
                except json.JSONDecodeError:
                    self.logger.warning(f"Could not parse LangChain parameter result as JSON: {raw_result}")
                    # Fall back to rule-based approach

            except Exception as e:
                self.logger.error(f"Error using LangChain for parameter extraction: {e}")
                # Fall back to rule-based approach
        
        # Rule-based parameter extraction
        parameters = {}
        
        # Extract model IDs
        parameters["model_ids"] = self._extract_model_mentions(query_text)
        
        # Extract metrics of interest
        metrics = []
        for match in re.finditer(self.metric_pattern, query_text.lower()):
            metrics.append(match.group(1))
        if metrics:
            parameters["metrics"] = metrics
        
        # Extract filters
        filters = {}
        for filter_name, pattern in self.filter_patterns.items():
            for match in re.finditer(pattern, query_text.lower()):
                if filter_name == "architecture":
                    filters["architecture"] = match.group(1)
                elif filter_name == "framework":
                    filters["framework"] = match.group(1)
                elif filter_name == "params":
                    filters["params"] = {
                        "operator": match.group(2),
                        "value": match.group(3)
                    }
                elif filter_name == "date":
                    filters["date"] = {
                        "field": match.group(1),
                        "operator": match.group(2),
                        "value": match.group(3)
                    }
        if filters:
            parameters["filters"] = filters
        
        # Extract result limit
        limit_match = re.search(self.limit_pattern, query_text.lower())
        if limit_match:
            parameters["limit"] = int(limit_match.group(2))
        
        # Extract sorting criteria
        sort_match = re.search(self.sort_pattern, query_text.lower())
        if sort_match:
            parameters["sort_by"] = {
                "field": sort_match.group(3),
                "order": sort_match.group(4) if sort_match.group(4) else "descending"
            }
        
        # Add intent-specific parameter extraction
        if intent == QueryIntent.COMPARISON:
            parameters.update(self._extract_comparison_parameters(query_text))
        elif intent == QueryIntent.NOTEBOOK:
            parameters.update(self._extract_notebook_parameters(query_text))
        elif intent == QueryIntent.IMAGE_SEARCH:
            parameters.update(self._extract_image_parameters(query_text))
        
        return parameters
    
    def _extract_model_mentions(self, query_text: str) -> List[str]:
        """
        Extract mentions of model IDs or names from query text.
        
        Args:
            query_text: The query text to extract from
            
        Returns:
            List of model identifiers
        """
        model_ids = []
        
        # Try to extract explicit model_id mentions
        for match in re.finditer(self.model_id_pattern, query_text.lower()):
            model_ids.append(match.group(2))
        
        # Check for model family mentions
        doc = self.nlp(query_text)
        for ent in doc.ents:
            if ent.label_ in ["ORG", "PRODUCT"]:
                model_ids.append(ent.text)
        
        # Check for common model family keywords
        for family in self.model_families:
            matches = re.finditer(r'\b' + re.escape(family) + r'[-_]?(\d+|v\d+)?\b', query_text.lower())
            for match in matches:
                model_ids.append(match.group(0))
        
        # Deduplicate and clean
        return list(set(model_ids))
    
    def _extract_comparison_parameters(self, query_text: str) -> Dict[str, Any]:
        """
        Extract comparison-specific parameters.
        
        Args:
            query_text: The query text to extract from
            
        Returns:
            Dictionary of comparison parameters
        """
        params = {}
        
        # Extract comparison dimensions
        dimensions = []
        dimension_pattern = r"(compare|comparing|comparison) (on|by|in terms of|regarding) ([\w\s,]+)"
        match = re.search(dimension_pattern, query_text.lower())
        if match:
            # Split by commas or 'and' and clean up
            dims = re.split(r',|\sand\s', match.group(3))
            dimensions = [dim.strip() for dim in dims if dim.strip()]
        
        if dimensions:
            params["comparison_dimensions"] = dimensions
        
        # Extract visualization preference
        if re.search(r'(show|display|visualize|plot|graph|chart)', query_text.lower()):
            params["visualize"] = True
        
        return params
    
    def _extract_notebook_parameters(self, query_text: str) -> Dict[str, Any]:
        """
        Extract notebook generation specific parameters.
        
        Args:
            query_text: The query text to extract from
            
        Returns:
            Dictionary of notebook parameters
        """
        params = {}
        
        # Extract analysis type
        analysis_types = []
        analysis_pattern = r"(analyze|analysis|examine|study|investigate) ([\w\s,]+)"
        match = re.search(analysis_pattern, query_text.lower())
        if match:
            # Split by commas or 'and' and clean up
            types = re.split(r',|\sand\s', match.group(2))
            analysis_types = [t.strip() for t in types if t.strip()]
        
        if analysis_types:
            params["analysis_types"] = analysis_types
        
        # Check for dataset mention
        dataset_pattern = r"(dataset|data)[:\s]+([\w\s-]+)"
        match = re.search(dataset_pattern, query_text.lower())
        if match:
            params["dataset"] = match.group(2).strip()
        
        # Check for resource constraints
        resource_pattern = r"(using|with) ([\w\s]+) (resources|gpu|memory|cpu)"
        match = re.search(resource_pattern, query_text.lower())
        if match:
            params["resources"] = match.group(2).strip()
        
        return params
    
    def _extract_image_parameters(self, query_text: str) -> Dict[str, Any]:
        """
        Extract image search specific parameters.
        
        Args:
            query_text: The query text to extract from
            
        Returns:
            Dictionary of image search parameters
        """
        params = {}
        
        # Extract prompt terms
        prompt_pattern = r"(prompt|prompts|text)[:\s]+[\"']?([\w\s,]+)[\"']?"
        match = re.search(prompt_pattern, query_text.lower())
        if match:
            params["prompt_terms"] = match.group(2).strip()
        
        # Extract style tags
        style_pattern = r"(style|type|category|look)[:\s]+[\"']?([\w\s,]+)[\"']?"
        match = re.search(style_pattern, query_text.lower())
        if match:
            # Split by commas and clean up
            styles = re.split(r',|\sand\s', match.group(2))
            params["style_tags"] = [style.strip() for style in styles if style.strip()]
        
        # Extract resolution preference
        resolution_pattern = r"(resolution|size|dimensions)[:\s]+(\d+)\s*[x×]\s*(\d+)"
        match = re.search(resolution_pattern, query_text.lower())
        if match:
            params["resolution"] = {
                "width": int(match.group(2)),
                "height": int(match.group(3))
            }
        
        return params
    
    def preprocess_query(self, query_text: str) -> str:
        """
        Preprocess a query for searching.
        
        Args:
            query_text: The raw query text
            
        Returns:
            Preprocessed query text
        """
        # Basic cleaning
        query_text = query_text.strip()
        
        # Use spaCy for tokenization and lemmatization
        doc = self.nlp(query_text)
        
        # Keep relevant tokens (remove stopwords, punctuation)
        tokens = []
        for token in doc:
            if (not token.is_stop and not token.is_punct and not token.is_space and 
                len(token.text.strip()) > 1):
                # Use lemma for standardization
                tokens.append(token.lemma_.lower())
        
        # Handling of technical terms and model names
        # Don't lemmatize technical terms or model names
        processed_text = []
        skip_indices = set()
        
        # Identify spans that should be preserved as-is
        for ent in doc.ents:
            if ent.label_ in ["PRODUCT", "ORG", "GPE", "PERSON"]:
                for i in range(ent.start, ent.end):
                    skip_indices.add(i)
                processed_text.append(ent.text)
        
        # Add tokens not part of preserved spans
        for i, token in enumerate(doc):
            if i not in skip_indices and not token.is_stop and not token.is_punct and not token.is_space:
                processed_text.append(token.lemma_.lower())
        
        # Join processed tokens
        return " ".join(processed_text)
        
