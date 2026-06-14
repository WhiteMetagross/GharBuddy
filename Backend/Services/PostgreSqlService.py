import os
import json
from contextlib import contextmanager

class PostgreSqlService:
    def __init__(self):
        self.postgresMode = "mock"
        self.pool = None
        self.hasPgVector = False
        
        # Local state structure mimicking PostgreSQL database tables
        self.mockDevices = {
            "geyser": {"name": "Bathroom Geyser", "status": "OFF", "wattage": 2000},
            "poojaLights": {"name": "Pooja Room Lights", "status": "OFF", "wattage": 40},
            "waterMotor": {"name": "Water Pump Motor", "status": "OFF", "wattage": 750},
            "inverterBackup": {"name": "Inverter Charger", "status": "NORMAL_CHARGE", "wattage": 150},
            "livingRoomLights": {"name": "Living Room Lights", "status": "ON", "wattage": 80},
            "television": {"name": "Smart TV", "status": "ON", "wattage": 120},
            "airConditioner": {"name": "Air Conditioner", "status": "OFF", "wattage": 1500},
            "speakerSystem": {"name": "Alexa Smart Speaker", "status": "NORMAL", "wattage": 10}
        }
        self.mockLogs = []
        self.mockEnergy = {
            "totalSavedWh": 4200,
            "rupeesSaved": 34,
            "peakPowerAvoidedW": 750,
            "inverterBatteryCharge": 85
        }
        self.mockVectorIndex = []
        self.mockEmbeddingCache = {}
        
        self.initializeDefaultRules()
        self.connectDb()

    @contextmanager
    def get_db_connection(self):
        """
        Thread-safe context manager to checkout and checkin database connections from the pool.
        """
        conn = None
        if self.postgresMode == "live" and self.pool:
            try:
                conn = self.pool.getconn()
                yield conn
            except Exception as e:
                print(f"PostgreSQL Pool checkout error: {e}")
                yield None
            finally:
                if conn:
                    try:
                        self.pool.putconn(conn)
                    except Exception:
                        pass
        else:
            yield None

    def connectDb(self):
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_user = os.getenv("DB_USER", "")
        db_password = os.getenv("DB_PASSWORD", "")
        db_name = os.getenv("DB_NAME", "")

        if not db_user or not db_name:
            print("PostgreSQL configuration credentials (DB_USER/DB_NAME) missing in .env. Running in Mock Mode.")
            self.postgresMode = "mock"
            return

        try:
            from psycopg2.pool import ThreadedConnectionPool
            print(f"Creating PostgreSQL connection pool at {db_host}:{db_port}...")
            self.pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                host=db_host,
                port=db_port,
                user=db_user,
                password=db_password,
                database=db_name,
                connect_timeout=3
            )
            self.postgresMode = "live"
            print("PostgreSQL connection pool initialized successfully.")
            
            # Check for pgvector extension
            try:
                with self.get_db_connection() as conn:
                    if conn:
                        conn.autocommit = True
                        with conn.cursor() as cur:
                            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                            self.hasPgVector = True
                            print("pgvector extension detected and verified successfully.")
            except Exception as e:
                self.hasPgVector = False
                print(f"pgvector extension is not available: {e}. Falling back to storing embeddings as JSON/text.")
            
            # Setup database tables
            self.createTables()
            
        except Exception as e:
            self.postgresMode = "mock"
            print(f"Failed to connect to PostgreSQL pool: {e}. Falling back to developer-friendly Mock Mode.")

    def createTables(self):
        if self.postgresMode != "live":
            return
        
        try:
            with self.get_db_connection() as conn:
                if not conn:
                    return
                conn.autocommit = True
                with conn.cursor() as cur:
                    # 1. Devices Table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS Devices (
                            deviceId VARCHAR(50) PRIMARY KEY,
                            deviceName VARCHAR(100),
                            status VARCHAR(50),
                            wattage INT
                        );
                    """)
                    
                    # 2. EventLogs Table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS EventLogs (
                            eventId SERIAL PRIMARY KEY,
                            sensorId VARCHAR(50),
                            value VARCHAR(200),
                            timestamp VARCHAR(50)
                        );
                    """)
                    
                    # 3. EnergyStats Table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS EnergyStats (
                            id INT PRIMARY KEY DEFAULT 1,
                            totalSavedWh INT,
                            rupeesSaved INT,
                            peakPowerAvoidedW INT,
                            inverterCharge INT,
                            CONSTRAINT single_row CHECK (id = 1)
                        );
                    """)
                    
                    # 4. VectorIndex Table (pgvector vs JSON fallback)
                    if self.hasPgVector:
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS VectorIndex (
                                ruleId SERIAL PRIMARY KEY,
                                content TEXT,
                                vector vector(1536),
                                category VARCHAR(50)
                            );
                        """)
                        try:
                            cur.execute("CREATE INDEX IF NOT EXISTS vector_cosine_idx ON VectorIndex USING hnsw (vector vector_cosine_ops);")
                            print("Postgres HNSW vector index verified.")
                        except Exception as idx_err:
                            print(f"Skipped HNSW index creation: {idx_err}. Using default scanning.")
                    else:
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS VectorIndex (
                                ruleId SERIAL PRIMARY KEY,
                                content TEXT,
                                vector TEXT,
                                category VARCHAR(50)
                            );
                        """)
                    
                    # 5. EmbeddingCache Table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS EmbeddingCache (
                            textHash VARCHAR(64) PRIMARY KEY,
                            inputText TEXT,
                            embedding TEXT
                        );
                    """)
                    
                    # Seed initial rows if empty
                    # Seed Devices
                    cur.execute("SELECT COUNT(*) FROM Devices;")
                    if cur.fetchone()[0] == 0:
                        for deviceId, dev in self.mockDevices.items():
                            cur.execute(
                                "INSERT INTO Devices (deviceId, deviceName, status, wattage) VALUES (%s, %s, %s, %s);",
                                (deviceId, dev["name"], dev["status"], dev["wattage"])
                            )
                        print("Devices table seeded.")

                    # Seed EnergyStats
                    cur.execute("SELECT COUNT(*) FROM EnergyStats;")
                    if cur.fetchone()[0] == 0:
                        cur.execute(
                            "INSERT INTO EnergyStats (id, totalSavedWh, rupeesSaved, peakPowerAvoidedW, inverterCharge) VALUES (1, %s, %s, %s, %s);",
                            (self.mockEnergy["totalSavedWh"], self.mockEnergy["rupeesSaved"], self.mockEnergy["peakPowerAvoidedW"], self.mockEnergy["inverterBatteryCharge"])
                        )
                        print("EnergyStats table seeded.")

                    # Seed Default Vector Rules
                    cur.execute("SELECT COUNT(*) FROM VectorIndex;")
                    if cur.fetchone()[0] == 0:
                        for rule in self.mockVectorIndex:
                            vec_str = json.dumps(rule["vector"])
                            if self.hasPgVector:
                                cur.execute(
                                    "INSERT INTO VectorIndex (content, vector, category) VALUES (%s, %s, %s);",
                                    (rule["content"], rule["vector"], rule["category"])
                                )
                            else:
                                cur.execute(
                                    "INSERT INTO VectorIndex (content, vector, category) VALUES (%s, %s, %s);",
                                    (rule["content"], vec_str, rule["category"])
                                )
                        print("VectorIndex table seeded.")
                        
        except Exception as e:
            print(f"Error initializing SQL tables: {e}")

    def getMockEmbedding(self, text):
        vector = [0.02] * 1536
        lowerText = text.lower()
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

    def initializeDefaultRules(self):
        defaultRules = [
            ("Bathroom motion detected during morning wake hours matches bath routine. Preheat geyser.", "routine"),
            ("On fasting days (Navratri, Shivratri, Ekadashi), suppress cooking appliance reminders.", "cultural"),
            ("Pooja room motion during prayer hours dims living room TV/speaker volume and turns on prayer lighting.", "cultural"),
            ("High load shedding risk (85%+) requires shutting down heavy loads (washing machine, AC, geyser) and precharging the inverter.", "safety"),
            ("Water motor runtime exceeding 20 minutes indicates leak hazard. Shut off motor automatically.", "safety"),
            ("Study hours (tuition window) require dimming living room speaker volume to minimum.", "routine"),
            ("Late night bedtime patterns require shutting down TV and placing all appliances on standby.", "routine")
        ]
        for rule, cat in defaultRules:
            mockVector = self.getMockEmbedding(rule)
            self.mockVectorIndex.append({
                "content": rule,
                "vector": mockVector,
                "category": cat
            })

    def getDevices(self):
        print("[SQL Log] SELECT deviceId, deviceName, status, wattage FROM Devices;")
        with self.get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT deviceId, deviceName, status, wattage FROM Devices;")
                        rows = cur.fetchall()
                        devices = {}
                        for row in rows:
                            devices[row[0]] = {
                                "name": row[1],
                                "status": row[2],
                                "wattage": row[3]
                            }
                        return devices
                except Exception as e:
                    print(f"SQL Error in getDevices: {e}. Falling back to mock data.")
        return self.mockDevices

    def updateDevice(self, deviceId, status):
        print(f"[SQL Log] UPDATE Devices SET status = '{status}' WHERE deviceId = '{deviceId}';")
        with self.get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE Devices SET status = %s WHERE deviceId = %s;",
                            (status, deviceId)
                        )
                        return True
                except Exception as e:
                    print(f"SQL Error in updateDevice: {e}. Falling back to mock data.")
        
        if deviceId in self.mockDevices:
            self.mockDevices[deviceId]["status"] = status
            return True
        return False

    def logEvent(self, sensorId, value, timestamp):
        print(f"[SQL Log] INSERT INTO EventLogs (sensorId, value, timestamp) VALUES ('{sensorId}', '{value}', '{timestamp}');")
        with self.get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO EventLogs (sensorId, value, timestamp) VALUES (%s, %s, %s);",
                            (sensorId, value, timestamp)
                        )
                    return
                except Exception as e:
                    print(f"SQL Error in logEvent: {e}. Falling back to mock storage.")
        
        self.mockLogs.append({
            "sensorId": sensorId,
            "value": value,
            "timestamp": timestamp
        })

    def getRecentLogs(self, count=5):
        print(f"[SQL Log] SELECT sensorId, value, timestamp FROM EventLogs ORDER BY eventId DESC LIMIT {count};")
        with self.get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT sensorId, value, timestamp FROM EventLogs ORDER BY eventId DESC LIMIT %s;",
                            (count,)
                        )
                        rows = cur.fetchall()
                        logs = []
                        for row in rows:
                            logs.append({
                                "sensorId": row[0],
                                "value": row[1],
                                "timestamp": row[2]
                            })
                        return list(reversed(logs))
                except Exception as e:
                    print(f"SQL Error in getRecentLogs: {e}. Falling back to mock logs.")
        return self.mockLogs[-count:]

    def getEnergyStats(self):
        print("[SQL Log] SELECT totalSavedWh, rupeesSaved, peakPowerAvoidedW, inverterCharge FROM EnergyStats LIMIT 1;")
        with self.get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT totalSavedWh, rupeesSaved, peakPowerAvoidedW, inverterCharge FROM EnergyStats LIMIT 1;")
                        row = cur.fetchone()
                        if row:
                            return {
                                "totalSavedWh": row[0],
                                "rupeesSaved": row[1],
                                "peakPowerAvoidedW": row[2],
                                "inverterBatteryCharge": row[3]
                            }
                except Exception as e:
                    print(f"SQL Error in getEnergyStats: {e}. Falling back to mock stats.")
        return self.mockEnergy

    def updateEnergyStats(self, savedWh, rupees):
        print(f"[SQL Log] UPDATE EnergyStats SET totalSavedWh = totalSavedWh + {savedWh}, rupeesSaved = rupeesSaved + {rupees};")
        with self.get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE EnergyStats SET totalSavedWh = totalSavedWh + %s, rupeesSaved = rupeesSaved + %s;",
                            (int(savedWh), int(rupees))
                        )
                    return
                except Exception as e:
                    print(f"SQL Error in updateEnergyStats: {e}. Falling back to mock.")
        
        self.mockEnergy["totalSavedWh"] += int(savedWh)
        self.mockEnergy["rupeesSaved"] += int(rupees)

    def setInverterCharge(self, percentage):
        print(f"[SQL Log] UPDATE EnergyStats SET inverterCharge = {percentage};")
        with self.get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE EnergyStats SET inverterCharge = %s;",
                            (percentage,)
                        )
                    return
                except Exception as e:
                    print(f"SQL Error in setInverterCharge: {e}. Falling back to mock.")
        
        self.mockEnergy["inverterBatteryCharge"] = max(0, min(100, percentage))

    def getVectors(self):
        print("[SQL Log] SELECT ruleId, content, vector, category FROM VectorIndex;")
        with self.get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT ruleId, content, vector, category FROM VectorIndex;")
                        rows = cur.fetchall()
                        records = []
                        for row in rows:
                            vector_val = row[2]
                            if isinstance(vector_val, str):
                                try:
                                    vector_val = json.loads(vector_val)
                                except Exception:
                                    pass
                            records.append({
                                "content": row[1],
                                "vector": vector_val,
                                "category": row[3]
                            })
                        return records
                except Exception as e:
                    print(f"SQL Error in getVectors: {e}. Falling back to mock index.")
        return self.mockVectorIndex

    def insertVectorRule(self, content, vector, category):
        try:
            print(f"[SQL Log] INSERT INTO VectorIndex (content, vector, category) VALUES ('{content[:30]}...', <float_array>, '{category}');")
        except UnicodeEncodeError:
            safe_content = content[:30].encode('ascii', errors='replace').decode('ascii')
            print(f"[SQL Log] INSERT INTO VectorIndex (content, vector, category) VALUES ('{safe_content}...', <float_array>, '{category}');")
        with self.get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cur:
                        if self.hasPgVector:
                            vector_str = "[" + ",".join(map(str, vector)) + "]"
                            cur.execute(
                                "INSERT INTO VectorIndex (content, vector, category) VALUES (%s, %s, %s);",
                                (content, vector_str, category)
                            )
                        else:
                            cur.execute(
                                "INSERT INTO VectorIndex (content, vector, category) VALUES (%s, %s, %s);",
                                (content, json.dumps(vector), category)
                            )
                    return
                except Exception as e:
                    print(f"SQL Error in insertVectorRule: {e}. Falling back to mock storage.")
        
        self.mockVectorIndex.append({
            "content": content,
            "vector": vector,
            "category": category
        })

    def getEmbeddingFromCache(self, textHash):
        with self.get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT embedding FROM EmbeddingCache WHERE textHash = %s;", (textHash,))
                        row = cur.fetchone()
                        if row:
                            return json.loads(row[0])
                except Exception as e:
                    print(f"SQL Error in getEmbeddingFromCache: {e}")
        return self.mockEmbeddingCache.get(textHash)

    def insertEmbeddingIntoCache(self, textHash, inputText, embedding):
        with self.get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO EmbeddingCache (textHash, inputText, embedding) VALUES (%s, %s, %s) ON CONFLICT (textHash) DO NOTHING;",
                            (textHash, inputText, json.dumps(embedding))
                        )
                    return
                except Exception as e:
                    print(f"SQL Error in insertEmbeddingIntoCache: {e}")
        self.mockEmbeddingCache[textHash] = embedding

    def deleteVectorRule(self, content):
        with self.get_db_connection() as conn:
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM VectorIndex WHERE content = %s;", (content,))
                    return
                except Exception as e:
                    print(f"SQL Error in deleteVectorRule: {e}")
        self.mockVectorIndex = [r for r in self.mockVectorIndex if r["content"] != content]
