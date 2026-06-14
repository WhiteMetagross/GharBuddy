import json
import math
import time
from datetime import datetime, timezone
from Backend.Config.AppConfig import AppConfig

class VectorStoreService:
    def __init__(self, postgresService):
        self.db = postgresService
        self.bedrockClient = None
        # Issue #20 — cache hit/miss counters
        self._cacheHits = 0
        self._cacheMisses = 0
        # Issue #21 — auto-consolidation tracking
        self.lastConsolidationTime = None
        self.initBedrockClient()

    def initBedrockClient(self):
        if not AppConfig.mockMode:
            try:
                import boto3
                self.bedrockClient = boto3.client(
                    service_name="bedrock-runtime",
                    region_name=AppConfig.awsRegion
                )
                print("VectorStore: AWS Bedrock client initialized successfully.")
            except Exception as e:
                print(f"VectorStore: Bedrock client initialization skipped: {e}. Using local embeddings engine.")

    def getEmbedding(self, text):
        """
        Generates text embedding using Bedrock (Titan) or a deterministic local proxy generator,
        utilizing a SQL/mock caching layer to prevent duplicate API invocations.
        """
        import hashlib
        textHash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        
        cached = self.db.getEmbeddingFromCache(textHash)
        if cached is not None:
            self._cacheHits += 1
            print(f"[Cache Log] HIT for embedding text: '{text[:30]}...'")
            return cached

        self._cacheMisses += 1
        print(f"[Cache Log] MISS for embedding text: '{text[:30]}...'")
        
        embedding = None
        if AppConfig.mockMode or not self.bedrockClient:
            embedding = self.getMockEmbedding(text)
        else:
            try:
                body = json.dumps({
                    "inputText": text
                })
                response = self.bedrockClient.invoke_model(
                    modelId="amazon.titan-embed-text-v1",
                    body=body
                )
                responseBody = json.loads(response.get("body").read())
                embedding = responseBody.get("embedding")
            except Exception as e:
                print(f"Error querying Bedrock Titan Embeddings: {e}. Falling back to mock embeddings.")
                embedding = self.getMockEmbedding(text)

        if embedding is not None:
            self.db.insertEmbeddingIntoCache(textHash, text, embedding)
            
        return embedding

    def getMockEmbedding(self, text):
        """
        Creates a deterministic 1536-dimensional vector for localized offline evaluations.
        Binds coordinates to matching semantic terms to align similarity models.
        """
        vector = [0.02] * 1536
        lowerText = text.lower()

        # Semantic segment coordinates mapping
        keywords = {
            "geyser": 5,
            "toilet": 5,
            "bathroom": 5,
            "bath": 5,
            "pooja": 15,
            "prayer": 15,
            "lights": 15,
            "fasting": 25,
            "cooker": 35,
            "whistle": 35,
            "kitchen": 35,
            "motor": 45,
            "water": 45,
            "leak": 45,
            "shedding": 55,
            "inverter": 55,
            "power": 55,
            "cut": 55,
            "study": 65,
            "tuition": 65,
            "bedtime": 75,
            "sleep": 75,
            "night": 75
        }

        for word, index in keywords.items():
            if word in lowerText:
                for i in range(index * 10, (index + 1) * 10):
                    vector[i] = 1.0

        return vector

    def getCacheStats(self):
        """Issue #20 — Returns embedding cache hit/miss statistics."""
        totalRequests = self._cacheHits + self._cacheMisses
        hitRate = (self._cacheHits / totalRequests) if totalRequests > 0 else 0.0
        return {
            "hits": self._cacheHits,
            "misses": self._cacheMisses,
            "hitRate": hitRate,
            "totalRequests": totalRequests,
        }

    def evictOldestEmbeddings(self, keepCount=500):
        """Issue #20 — Evicts oldest embeddings keeping only the most recent keepCount entries."""
        self.db.evictOldEmbeddings(maxEntries=keepCount)

    def addRule(self, content, category):
        vector = self.getEmbedding(content)
        self.db.insertVectorRule(content, vector, category)

    def querySimilarRules(self, queryText, topK=2):
        """
        Calculates cosine distance over stored rules and returns top-K results.
        Uses native pgvector distance operator <=> if active, else falls back to Python.
        Applies a minimum similarity score threshold of 0.65 for Bedrock, and 0.20 for mock mode.
        """
        threshold = 0.65 if self.bedrockClient else 0.20

        if self.db.postgresMode == "live" and self.db.hasPgVector:
            try:
                queryVector = self.getEmbedding(queryText)
                vector_str = "[" + ",".join(map(str, queryVector)) + "]"
                with self.db.get_db_connection() as conn:
                    if conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                "SELECT content, category, (vector <=> %s) AS distance FROM VectorIndex ORDER BY distance ASC LIMIT %s;",
                                (vector_str, topK)
                            )
                            rows = cur.fetchall()
                            scoredRecords = []
                            for row in rows:
                                distance = row[2]
                                similarity = 1.0 - float(distance) if distance is not None else 0.0
                                # Apply threshold
                                if similarity >= threshold:
                                    scoredRecords.append({
                                        "content": row[0],
                                        "category": row[1],
                                        "similarity": similarity
                                    })
                            return scoredRecords
            except Exception as e:
                print(f"Error in native pgvector similarity query: {e}. Falling back to Python calculations.")

        queryVector = self.getEmbedding(queryText)
        return self.querySimilarRulesChunked(queryVector, topK=topK, threshold=threshold)

    def querySimilarRulesChunked(self, queryVector, topK=2, threshold=0.20, chunkSize=50):
        """
        Issue #18 — Iterate over VectorIndex in chunks instead of loading all records at once.
        Uses chunked processing to avoid OOM on large rule sets.
        """
        t0 = time.monotonic()
        total = 0
        bestResults = []
        offset = 0

        while True:
            chunk = self.db.getVectorsChunk(offset=offset, limit=chunkSize)
            if not chunk:
                break
            for rec in chunk:
                if not isinstance(rec.get("vector"), list):
                    continue
                similarity = self.calculateCosineSimilarity(queryVector, rec["vector"])
                if similarity >= threshold:
                    bestResults.append({
                        "content": rec["content"],
                        "category": rec["category"],
                        "similarity": similarity
                    })
            total += len(chunk)
            offset += chunkSize
            if len(chunk) < chunkSize:
                break  # Last chunk

        elapsed = (time.monotonic() - t0) * 1000
        print(f"[RAG] Python fallback chunked scan: {total} rules in {elapsed:.1f}ms")

        bestResults.sort(key=lambda x: x["similarity"], reverse=True)
        return bestResults[:topK]

    def calculateCosineSimilarity(self, v1, v2):
        dotProduct = sum(x * y for x, y in zip(v1, v2))
        magnitude1 = math.sqrt(sum(x * x for x in v1))
        magnitude2 = math.sqrt(sum(x * x for x in v2))
        if not magnitude1 or not magnitude2:
            return 0.0
        return dotProduct / (magnitude1 * magnitude2)

    def shouldAutoConsolidate(self, intervalHours=168):
        """Issue #21 — Returns True if enough time has passed since last consolidation (default: weekly)."""
        if self.lastConsolidationTime is None:
            return True
        elapsed = datetime.now(timezone.utc) - self.lastConsolidationTime
        return elapsed.total_seconds() >= intervalHours * 3600

    def getConsolidationStats(self) -> dict:
        """Returns stats useful for deciding when to run consolidation. Issue #21."""
        total = self.db.getVectorCount()
        # Count by category
        records = self.db.getVectors()
        category_counts = {}
        for r in records:
            cat = r.get("category", "unknown")
            category_counts[cat] = category_counts.get(cat, 0) + 1
        return {
            "totalRules": total,
            "categoryBreakdown": category_counts,
            "recommendConsolidation": total > 20,
        }

    def scheduleAutoConsolidation(self, bedrockService, similarityThreshold=0.85):
        """
        Issue #21 — Runs consolidation only if total rules > 20 (avoids over-consolidating small sets).
        Returns stats dict with consolidated count, totalBefore, and totalAfter.
        """
        records = self.db.getVectors()
        totalBefore = len(records)

        if totalBefore <= 20:
            return {
                "consolidated": 0,
                "skipped": f"Only {totalBefore} rules — minimum 21 required for auto-consolidation",
                "totalBefore": totalBefore,
                "totalAfter": totalBefore,
            }

        count = self.consolidateRules(bedrockService)
        self.lastConsolidationTime = datetime.now(timezone.utc)

        recordsAfter = self.db.getVectors()
        totalAfter = len(recordsAfter)

        return {
            "consolidated": count,
            "skipped": None,
            "totalBefore": totalBefore,
            "totalAfter": totalAfter,
        }

    def autoConsolidate(self, bedrockService):
        """Issue #21 — Runs consolidateRules and updates lastConsolidationTime."""
        count = self.consolidateRules(bedrockService)
        self.lastConsolidationTime = datetime.now(timezone.utc)
        return count

    def consolidateRules(self, bedrockService):
        """
        Scans all rules in the vector store, clusters redundant ones with similarity >= 0.85,
        and uses Bedrock to consolidate them.
        """
        records = self.db.getVectors()
        if len(records) < 2:
            return 0

        consolidated_count = 0
        skip_indices = set()

        for i in range(len(records)):
            if i in skip_indices:
                continue
            r1 = records[i]
            v1 = r1["vector"]
            rule1_text = r1["content"]
            category1 = r1["category"]

            for j in range(i + 1, len(records)):
                if j in skip_indices:
                    continue
                r2 = records[j]
                v2 = r2["vector"]
                rule2_text = r2["content"]
                category2 = r2["category"]

                # Only consolidate rules within the same category
                if category1 != category2:
                    continue

                similarity = self.calculateCosineSimilarity(v1, v2)
                # For mock embedding vectors we might have similar stubs. We use 0.85 for real embeddings.
                # In mock mode, keywords match exact segments.
                if similarity >= 0.85:
                    print(f"[Consolidation Log] Highly similar rules detected (Similarity: {similarity:.2f}):")
                    print(f"  1) '{rule1_text}'")
                    print(f"  2) '{rule2_text}'")

                    # Invoke Bedrock to merge the rules
                    new_rule = bedrockService.generateConsolidatedRule(rule1_text, rule2_text)
                    print(f"  Consolidated Output: '{new_rule}'")

                    # Delete original rules from DB
                    self.db.deleteVectorRule(rule1_text)
                    self.db.deleteVectorRule(rule2_text)

                    # Insert the new consolidated rule
                    self.addRule(new_rule, category1)

                    # Mark indices to skip
                    skip_indices.add(i)
                    skip_indices.add(j)
                    consolidated_count += 1
                    break

        return consolidated_count

