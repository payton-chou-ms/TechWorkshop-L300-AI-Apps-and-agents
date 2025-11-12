"""
Azure AI Search Ingestion Script
Reads data from CSV and uploads to Azure AI Search as a vector database.
"""

import logging
import os
import pandas as pd
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    VectorSearchAlgorithmKind,
)
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
CSV_FILE = "data/updated_product_catalog(in).csv"
INDEX_NAME = "zava-product-catalog"
SEARCH_ENDPOINT = os.environ.get("SEARCH_ENDPOINT")
SEARCH_KEY = os.environ.get("SEARCH_KEY")

# Azure OpenAI for embeddings
"""
Azure AI Search Ingestion Script
Reads data from CSV and uploads to Azure AI Search as a vector database.
"""

import logging
import os
import pandas as pd
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    VectorSearchAlgorithmKind,
)
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
CSV_FILE = "data/updated_product_catalog(in).csv"
INDEX_NAME = "zava-product-catalog"
SEARCH_ENDPOINT = os.environ.get("SEARCH_ENDPOINT")
SEARCH_KEY = os.environ.get("SEARCH_KEY")

# Azure OpenAI for embeddings
AZURE_OPENAI_EMBEDDING_ENDPOINT = os.environ.get("AZURE_OPENAI_EMBEDDING_ENDPOINT")
EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
EMBEDDING_DIMENSIONS = 3072


def validate_environment():
    """Validate that all required environment variables are set."""
    logger.info("Validating environment variables...")
    missing = []
    
    if not SEARCH_ENDPOINT:
        missing.append("SEARCH_ENDPOINT")
    if not SEARCH_KEY:
        missing.append("SEARCH_KEY")
    if not AZURE_OPENAI_EMBEDDING_ENDPOINT:
        missing.append("AZURE_OPENAI_EMBEDDING_ENDPOINT")
    
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    logger.info("✓ All required environment variables are set")
    logger.info("")
    logger.info("NOTE: This script uses Azure IAM (Managed Identity / Azure CLI) for authentication.")
    logger.info("Make sure your account has the following role on Azure AI Foundry:")
    logger.info("  → Cognitive Services OpenAI User")
    logger.info("")


def create_or_update_index(index_client: SearchIndexClient):
    """
    Create or update the Azure AI Search index with vector search capabilities.
    """
    logger.info(f"Creating or updating index: {INDEX_NAME}")
    
    # Define index fields
    fields = [
        SearchField(
            name="ProductID",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
            sortable=True
        ),
        SearchField(
            name="ProductName",
            type=SearchFieldDataType.String,
            searchable=True,
            filterable=True,
            sortable=True
        ),
        SearchField(
            name="ProductCategory",
            type=SearchFieldDataType.String,
            searchable=True,
            filterable=True,
            facetable=True
        ),
        SearchField(
            name="ProductDescription",
            type=SearchFieldDataType.String,
            searchable=True
        ),
        SearchField(
            name="ProductPrice",
            type=SearchFieldDataType.Double,
            filterable=True,
            sortable=True
        ),
        SearchField(
            name="ProductImageUrl",
            type=SearchFieldDataType.String,
            filterable=False
        ),
        SearchField(
            name="content_for_vector",
            type=SearchFieldDataType.String,
            searchable=True
        ),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name="myHnswProfile"
        )
    ]
    
    # Configure vector search
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="myHnsw",
                kind=VectorSearchAlgorithmKind.HNSW,
                parameters={
                    "m": 4,
                    "efConstruction": 400,
                    "efSearch": 500,
                    "metric": "cosine"
                }
            )
        ],
        profiles=[
            VectorSearchProfile(
                name="myHnswProfile",
                algorithm_configuration_name="myHnsw"
            )
        ]
    )
    
    # Create the index
    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search
    )
    
    result = index_client.create_or_update_index(index)
    logger.info(f"✓ Index '{result.name}' created or updated successfully")
    return result


def load_data_from_csv(csv_path: str) -> pd.DataFrame:
    """
    Load data from CSV file.
    """
    logger.info(f"Loading data from CSV: {csv_path}")
    
    df = pd.read_csv(csv_path, encoding='cp1252')
    
    # Create content_for_vector field if it doesn't exist
    if 'content_for_vector' not in df.columns:
        df['content_for_vector'] = (
            df['ProductName'].fillna('').astype(str) + ' | ' +
            df['ProductCategory'].fillna('').astype(str) + ' | ' +
            df['ProductDescription'].fillna('').astype(str)
        )
    
    logger.info(f"✓ Loaded {len(df)} products from CSV")
    return df


def generate_embeddings(texts: list[str], openai_client: AzureOpenAI) -> list[list[float]]:
    """
    Generate embeddings for a list of texts using Azure OpenAI.
    """
    response = openai_client.embeddings.create(
        model=EMBEDDING_DEPLOYMENT,
        input=texts
    )
    return [item.embedding for item in response.data]


def upload_documents(search_client: SearchClient, df: pd.DataFrame, openai_client: AzureOpenAI):
    """
    Upload documents to Azure AI Search with vector embeddings.
    """
    logger.info(f"Uploading {len(df)} documents to Azure AI Search...")
    
    # Convert DataFrame to list of documents
    documents = []
    batch_size = 10  # Process embeddings in batches
    
    for i in range(0, len(df), batch_size):
        batch_df = df.iloc[i:i+batch_size]
        texts = batch_df['content_for_vector'].tolist()
        
        logger.info(f"Generating embeddings for batch {i//batch_size + 1}/{(len(df)-1)//batch_size + 1}...")
        embeddings = generate_embeddings(texts, openai_client)
        
        for idx, (_, row) in enumerate(batch_df.iterrows()):
            doc = {
                'ProductID': str(row['ProductID']),
                'ProductName': str(row['ProductName']),
                'ProductCategory': str(row['ProductCategory']),
                'ProductDescription': str(row['ProductDescription']),
                'ProductPrice': float(row['Price']),  # CSV uses 'Price'
                'ProductImageUrl': str(row['ImageURL']),  # CSV uses 'ImageURL'
                'content_for_vector': str(row['content_for_vector']),
                'content_vector': embeddings[idx]
            }
            documents.append(doc)
    
    # Upload documents in batches
    upload_batch_size = 50
    for i in range(0, len(documents), upload_batch_size):
        batch = documents[i:i+upload_batch_size]
        logger.info(f"Uploading batch {i//upload_batch_size + 1}/{(len(documents)-1)//upload_batch_size + 1}...")
        result = search_client.upload_documents(documents=batch)
        logger.info(f"✓ Uploaded {len(batch)} documents")
    
    logger.info(f"✓ All {len(documents)} documents uploaded successfully")


def main():
    """
    Main execution function.
    """
    try:
        logger.info("="*60)
        logger.info("Azure AI Search Ingestion Script")
        logger.info("="*60)
        
        # Step 1: Validate configuration
        logger.info("\n[Step 1/5] Validating configuration...")
        validate_environment()
        
        # Step 2: Create clients
        logger.info("\n[Step 2/5] Creating Azure clients...")
        credential = AzureKeyCredential(SEARCH_KEY)
        index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=credential)
        search_client = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=credential)
        
        # Extract base endpoint from AZURE_OPENAI_EMBEDDING_ENDPOINT
        # Format: https://aif-w2r4ntsieif4e.cognitiveservices.azure.com/openai/deployments/text-embedding-3-large/embeddings?api-version=2023-05-15
        openai_endpoint = AZURE_OPENAI_EMBEDDING_ENDPOINT
        if "/openai/deployments/" in openai_endpoint:
            openai_endpoint = "/".join(openai_endpoint.split("/")[:3])
        
        # Use DefaultAzureCredential for authentication (IAM-based)
        azure_credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            azure_credential,
            "https://cognitiveservices.azure.com/.default"
        )
        
        openai_client = AzureOpenAI(
            azure_endpoint=openai_endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2023-05-15"
        )
        logger.info("✓ Clients created successfully")
        
        # Step 3: Create or update index
        logger.info("\n[Step 3/5] Creating or updating search index...")
        create_or_update_index(index_client)
        
        # Step 4: Load data from CSV
        logger.info("\n[Step 4/5] Loading data from CSV...")
        df = load_data_from_csv(CSV_FILE)
        
        # Step 5: Upload documents with embeddings
        logger.info("\n[Step 5/5] Uploading documents to Azure AI Search...")
        upload_documents(search_client, df, openai_client)
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("✓ SUCCESS: Data ingestion to Azure AI Search completed!")
        logger.info(f"  Index name: {INDEX_NAME}")
        logger.info(f"  Total documents: {len(df)}")
        logger.info(f"  You can now query the index using Azure AI Search")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"\n✗ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
