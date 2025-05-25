# quantize_collection.py
from qdrant_client import QdrantClient
from qdrant_client.http import models
import os, logging, time

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

HOST = os.getenv("QDRANT_HOST", "178.156.156.250")
PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLL = os.getenv("QDRANT_COLLECTION", "caselaw_bge_base_v2")

def quantize():
    cli = QdrantClient(host=HOST, port=PORT, prefer_grpc=True, timeout=300)

    cfg = cli.get_collection(COLL).config.quantization_config
    if cfg and cfg.scalar:
        log.info("Collection already quantized – nothing to do.")
        return True

    try:
        cli.update_collection(
            collection_name=COLL,
            quantization_config=models.ScalarQuantization(
                scalar=models.ScalarQuantizationConfig(
                    type=models.ScalarType.INT8,
                    always_ram=True
                )
            )
        )
    except httpx.TransportError as e:
        log.error("Transport error (likely OOM): %s", e)
        return False

    deadline = time.time() + 7200  # 2 h safety
    while True:
        if time.time() > deadline:
            raise TimeoutError("Quantization exceeded 2 h")
        if cli.get_collection(COLL).status.value == "Green":
            break
        log.info("Rebuild in progress …")
        time.sleep(30)
    return True

if __name__ == "__main__":
    print("Success" if quantize() else "Failed")