"""
Diagnostic: can a Spark WORKER reach Azure OpenAI?
Runs the embedding call inside a UDF on a single row and surfaces
the real underlying exception instead of the swallowed 'Connection error'.
"""
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType


def make_diag_udf(endpoint, api_key, api_version, model_name):
    @F.udf(returnType=StringType())
    def diag_udf(text):
        import traceback
        import socket
        result = []

        # Test 1: raw DNS / TCP reachability to the host
        host = endpoint.replace("https://", "").replace("http://", "").rstrip("/")
        try:
            ip = socket.gethostbyname(host)
            result.append(f"DNS OK: {host} -> {ip}")
        except Exception as e:
            result.append(f"DNS FAILED: {type(e).__name__}: {e}")

        # Test 2: the actual embedding call, with full traceback
        try:
            from openai import AzureOpenAI
            client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_version=api_version,
                api_key=api_key,
                max_retries=5, # default is 2; the client does exponential backoff automatically
            )
            resp = client.embeddings.create(input=[text], model=model_name)
            result.append(f"EMBED OK: dim={len(resp.data[0].embedding)}")
        except Exception as e:
            result.append(f"EMBED FAILED: {type(e).__name__}: {e}")
            result.append(traceback.format_exc())

        return " | ".join(result)

    return diag_udf


def main():
    spark = SparkSession.builder.getOrCreate()

    from pyspark.dbutils import DBUtils
    dbutils = DBUtils(spark)
    scope = "compliance-assistant"
    endpoint = dbutils.secrets.get(scope=scope, key="AZURE_OPENAI_ENDPOINT")
    api_key = dbutils.secrets.get(scope=scope, key="AZURE_OPENAI_API_KEY")
    api_version = dbutils.secrets.get(scope=scope, key="AZURE_OPENAI_API_VERSION")
    model_name = dbutils.secrets.get(scope=scope, key="EMBEDDING_MODEL_NAME")

    diag_udf = make_diag_udf(endpoint, api_key, api_version, model_name)

    # One-row DataFrame, run the diagnostic on the worker
    df = spark.createDataFrame([("test sentence",)], ["chunk_text"])
    out = df.withColumn("diag", diag_udf(F.col("chunk_text")))

    # Pull the single result back to the driver and print it
    print("=" * 80)
    print(out.collect()[0]["diag"])
    print("=" * 80)


if __name__ == "__main__":
    main()