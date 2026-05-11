import os
import json
import logging
import random
import chromadb
from sentence_transformers import SentenceTransformer
from chromadb.utils import embedding_functions

# --- Configuration ---
DATA_DIR = "/home/william/projects/nlp_final_project/PTT-Crawler-master/data_Gossiping_2025"
DB_PATH = "/home/william/projects/nlp_final_project/PTT-Crawler-master/chroma_db"
MODEL_NAME = "all-MiniLM-L6-v2"
MAX_DOCUMENTS = 100000  # Cap for performance on old desktop

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_indexer():
    logger.info("Starting Local-powered JSON indexer (SAMPLED)...")
    
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)
    client = chromadb.PersistentClient(path=DB_PATH)
    
    try:
        client.delete_collection(name="ptt_gossip")
    except:
        pass
        
    collection = client.create_collection(
        name="ptt_gossip", 
        embedding_function=emb_fn
    )

    all_texts = []
    json_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".json")]
    
    # Sample from each file to maintain distribution
    files_per_sample = len(json_files)
    docs_per_file = MAX_DOCUMENTS // files_per_sample if files_per_sample > 0 else 0
    
    for filename in json_files:
        file_path = os.path.join(DATA_DIR, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    file_texts = []
                    for item in data:
                        if 'Content' in item and item['Content']:
                            file_texts.append(item['Content'])
                        if 'Responses' in item and isinstance(item['Responses'], list):
                            for resp in item['Responses']:
                                if 'Content' in resp and resp['Content']:
                                    file_texts.append(resp['Content'])
                    
                    # Sample from this file
                    if len(file_texts) > docs_per_file:
                        sampled = random.sample(file_texts, docs_per_file)
                        all_texts.extend(sampled)
                    else:
                        all_texts.extend(file_texts)
        except Exception as e:
            logger.error(f"Error reading {filename}: {e}")

    # Final cap to be absolutely sure
    if len(all_texts) > MAX_DOCUMENTS:
        all_texts = random.sample(all_texts, MAX_DOCUMENTS)

    logger.info(f"Extracted {len(all_texts)} sampled text segments from JSON files")

    batch_size = 64
    for i in range(0, len(all_texts), batch_size):
        batch = all_texts[i:i+batch_size]
        ids = [f"id_{j}" for j in range(i, i+len(batch))]
        
        try:
            collection.add(
                documents=batch,
                ids=ids
            )
            if i % 1000 == 0:
                logger.info(f"Indexed {i}/{len(all_texts)} segments...")
        except Exception as e:
            logger.error(f"Error indexing batch at {i}: {e}")

    logger.info(f"Successfully indexed {len(all_texts)} segments into {DB_PATH}")

if __name__ == "__main__":
    run_indexer()
