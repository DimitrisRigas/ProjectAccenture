"""
src/jobs/silver_chunking.py

Read extracted text from the Bronze pages table,
split each page/section into overlapping chunks,
add stable chunk identifiers,
and write the results to the Silver Delta table.

Input:
    accenture2026dbcks.team4.bronze_document_pages

Output:
    accenture2026dbcks.team4.silver_document_chunks
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType


CATALOG = "accenture2026dbcks"
SCHEMA = "team4"

BRONZE_PAGES_TABLE = f"{CATALOG}.{SCHEMA}.bronze_document_pages"
SILVER_CHUNK_TABLE = f"{CATALOG}.{SCHEMA}.silver_document_chunks"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


@F.udf(returnType=ArrayType(StringType()))
def chunk_text_udf(text):
    """
    Split one text field into overlapping chunks.

    Returns an empty list for null, empty, or whitespace-only text.
    Spark posexplode will then produce zero rows for that input row.
    """

    if not text or not text.strip():
        return []

    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=[
            "\n\n",
            "\n",
            ". ",
            "; ",
            ", ",
            " ",
            "",
        ],
    )

    return splitter.split_text(text)


def main():
    spark = SparkSession.builder.getOrCreate()

    bronze_pages = spark.read.table(BRONZE_PAGES_TABLE)

    silver_chunks = (
        bronze_pages
        .withColumn("chunks", chunk_text_udf(F.col("text")))
        .select(
            "*",
            F.posexplode("chunks").alias("chunk_index", "chunk_text"),
        )
        .drop("chunks", "text")
        .withColumn("chunk_text", F.trim(F.col("chunk_text")))
        .filter(F.col("chunk_text").isNotNull())
        .filter(F.length(F.col("chunk_text")) > 0)
        .withColumn("chunk_length", F.length(F.col("chunk_text")))
        .withColumn(
            "chunk_id",
            F.sha2(
                F.concat_ws(
                    "_",
                    F.col("document_id"),
                    F.coalesce(F.col("page_number").cast("string"), F.lit("no_page")),
                    F.coalesce(F.col("section_number").cast("string"), F.lit("no_section")),
                    F.col("chunk_index").cast("string"),
                ),
                256,
            ),
        )
        .withColumn("silver_loaded_at", F.current_timestamp())
    )

    (
        silver_chunks.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(SILVER_CHUNK_TABLE)
    )

    print(f"Silver chunks written to: {SILVER_CHUNK_TABLE}")
    print(f"Chunk size: {CHUNK_SIZE}")
    print(f"Chunk overlap: {CHUNK_OVERLAP}")


if __name__ == "__main__":
    main()