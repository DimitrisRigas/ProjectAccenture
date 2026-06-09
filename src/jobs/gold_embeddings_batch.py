"""
Read chunks from silver chunks table
and write the generated embeddings in gold embeddings table

Input: silver_document_chunks

Output: gold_chunk_embeddings

"""
import pandas as pd
from typing import Iterator
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, FloatType

CATALOG = "accenture2026dbcks"
SCHEMA = "team4"

SILVER_CHUNK_TABLE = f"{CATALOG}.{SCHEMA}.silver_document_chunks"
GOLD_EMBEDDINGS_TABLE = f"{CATALOG}.{SCHEMA}.gold_chunk_embeddings"

def make_embed_udf(endpoint, api_key, api_version, model_name):
    @F.pandas_udf(ArrayType(FloatType()))
    def embed_udf(batches: Iterator[pd.Series]) -> Iterator[pd.Series]:
        """
        Sets up the client ONCE per worker (not per batch) - efficient.
        """
        # Create client
        from openai import AzureOpenAI
        import time

        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_version=api_version,
            api_key=api_key,
            max_retries=5,
        )

        for batch in batches: # each batch is a pandas Series of chunk_texts
            texts = batch.tolist() # Convert Series to list of strings
            all_embeddings = [] # will collect one entry per text, in order
            SUB_BATCH_SIZE = 100 # Process in sub-batches of 100
            for i in range(0, len(texts), SUB_BATCH_SIZE):
                sub_batch = texts[i : i + SUB_BATCH_SIZE]
                # Non-empty texts
                empty_indexes = []
                non_empty_texts = []
                for pos,text in enumerate(sub_batch):
                    if not text or not text.strip():
                        empty_indexes.append(pos)
                    else:
                        non_empty_texts.append(text)

                # Call API with the list on non empty texts
                if non_empty_texts:
                    response = client.embeddings.create(
                        input=non_empty_texts,
                        model=model_name,
                    )
                    embeddings = [item.embedding for item in response.data]
                else: # Safeguard against empty sub-batch
                    embeddings = []

                # Rebuild a list of same length as sub_batch
                count = 0
                for j in range(len(sub_batch)):
                    if j in empty_indexes:
                        all_embeddings.append(None)
                        count += 1
                    else:
                        all_embeddings.append(embeddings[j - count])
                time.sleep(0.1)
            yield pd.Series(all_embeddings)  # yield a Series of vectors, same order

    return embed_udf


def main():
    # Start a spark session
    spark = SparkSession.builder.getOrCreate()

    # Fetch secrets
    from pyspark.dbutils import DBUtils
    dbutils = DBUtils(spark)
    scope = "compliance-assistant"
    endpoint = dbutils.secrets.get(scope=scope, key="AZURE_OPENAI_ENDPOINT")
    api_key = dbutils.secrets.get(scope=scope, key="AZURE_OPENAI_API_KEY")
    api_version = dbutils.secrets.get(scope=scope, key="AZURE_OPENAI_API_VERSION")
    model_name = dbutils.secrets.get(scope=scope, key="EMBEDDING_MODEL_NAME")

    embed_udf = make_embed_udf(endpoint, api_key, api_version, model_name)

    # Read input table
    df = spark.read.table(SILVER_CHUNK_TABLE)

    # Transform data
    gold = df.withColumn("embedding", embed_udf(F.col("chunk_text")))

    # Write output to table
    (
        gold.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(GOLD_EMBEDDINGS_TABLE)
    )

if __name__ == '__main__':
    main()

