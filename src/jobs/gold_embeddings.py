"""
src/jobs/gold_embeddings.py

Create a Gold vector-search-ready Delta table from Silver chunks.

Input:
    accenture2026dbcks.team4.silver_document_chunks

Output:
    accenture2026dbcks.team4.gold_document_embeddings

Important:
    This script does not manually calculate embeddings.
    It prepares the clean Gold source table.
    Databricks Vector Search / AI Search will calculate embeddings from chunk_text.
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


CATALOG = "accenture2026dbcks"
SCHEMA = "team4"

SILVER_CHUNKS_TABLE = f"{CATALOG}.{SCHEMA}.silver_document_chunks"
GOLD_EMBEDDINGS_TABLE = f"{CATALOG}.{SCHEMA}.gold_document_embeddings"


def main():
    spark = SparkSession.builder.getOrCreate()

    silver = spark.read.table(SILVER_CHUNKS_TABLE)

    gold = (
        silver
        .select(
            "chunk_id",
            "document_id",
            "celex",
            "short_title",
            "regulation_title",
            "regulation_category",
            "compliance_domain",
            "document_type",
            "language",
            "source_system",
            "source_url",
            "file_format",
            "source_file",
            "file_name",
            "page_number",
            "section_number",
            "chunk_index",
            "chunk_length",
            "chunk_text",
        )
        .filter(F.col("chunk_id").isNotNull())
        .filter(F.col("chunk_text").isNotNull())
        .filter(F.length(F.trim(F.col("chunk_text"))) > 0)
        .dropDuplicates(["chunk_id"])
        .withColumn("gold_loaded_at", F.current_timestamp())
    )

    (
        gold.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .option("delta.enableChangeDataFeed", "true")
        .saveAsTable(GOLD_EMBEDDINGS_TABLE)
    )

    spark.sql(
        f"""
        ALTER TABLE {GOLD_EMBEDDINGS_TABLE}
        SET TBLPROPERTIES (delta.enableChangeDataFeed = true)
        """
    )

    print(f"Gold table written to: {GOLD_EMBEDDINGS_TABLE}")


if __name__ == "__main__":
    main()