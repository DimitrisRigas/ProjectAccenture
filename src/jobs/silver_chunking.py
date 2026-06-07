"""
Read text from the Bronze pages table, 
split each page's text into overlapping chunks, 
and write the results to a new Silver table.

Input: bronze_document_pages - each row has a 'text' column 
plus metadata columns (celex, short title, page_number, etc)

Output: silver_document_chunks - many rows per input row, each with a chunk of text
plus the same metadata carried forward.
"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType

CATALOG = "accenture2026dbcks"
SCHEMA = "team4"

BRONZE_PAGES_TABLE = f"{CATALOG}.{SCHEMA}.bronze_document_pages"
SILVER_CHUNK_TABLE = f"{CATALOG}.{SCHEMA}.silver_document_chunks"

# Chunking parameters (mirrored inside chunk_text_udf for Spark serialization safety)
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


@F.udf(returnType=ArrayType(StringType()))
def chunk_text_udf(text):
    # If string is None, empty, or only white space
    if not text or not text.strip():
        return [] # will produce zero rows in spark
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    return splitter.split_text(text)


def main():
    # Start a spark session
    spark = SparkSession.builder.getOrCreate()

    # Read input table
    df = spark.read.table(BRONZE_PAGES_TABLE)

    # Transform the data
    """
    SELECT *, posexplode(chunks) AS (chunk_index, chunk_text)
    FROM (
        SELECT *, chunk_text_udf(text) AS chunks
        FROM bronze_document_pages
    )
    """
    silver = (
        df.withColumn("chunks", chunk_text_udf(F.col("text")))
        .select('*', F.posexplode("chunks").alias("chunk_index", "chunk_text"))
        .drop("chunks", "text")
    )

    # Write the output table
    (
        silver.write.format("delta")
            .mode("overwrite")
            .option("overwriteSchema", "true")
            .saveAsTable(SILVER_CHUNK_TABLE)
    )
    

if __name__ == "__main__":
    main()