# PostgreSQL + pgvector Setup Guide (Neon / AWS RDS)

## Option A: Neon (Recommended for hackathon)

### 1. Create Neon Project
1. Go to https://neon.tech and sign up (free tier)
2. Create new project: **GharBuddy**
3. Region: **AWS us-east-1** (matches Bedrock region)
4. Copy the **Connection String** from the dashboard

### 2. Enable pgvector Extension
In the Neon SQL Editor, run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 3. Set Environment Variables
Add to your deployment environment:
```
DB_HOST=<your-neon-hostname>.neon.tech
DB_PORT=5432
DB_USER=<your-neon-user>
DB_PASSWORD=<your-neon-password>
DB_NAME=neondb
```

### 4. Verify Connection
```bash
python3 -c "
import psycopg2
conn = psycopg2.connect(
    host='<your-neon-hostname>.neon.tech',
    port=5432,
    user='<your-neon-user>',
    password='<your-neon-password>',
    database='neondb',
    sslmode='require'
)
print('Connected:', conn.get_dsn_parameters())
conn.close()
"
```

GharBuddy will auto-create all tables on first startup via `createTables()`.

---

## Option B: AWS RDS PostgreSQL

### 1. Create RDS Instance
```bash
aws rds create-db-instance \
  --db-instance-identifier gharbuddy-prod \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 16.1 \
  --master-username postgres \
  --master-user-password <your-secure-password> \
  --allocated-storage 20 \
  --db-name gharbuddy \
  --publicly-accessible \
  --no-multi-az
```

### 2. Enable pgvector
After instance is available:
```bash
aws rds modify-db-instance \
  --db-instance-identifier gharbuddy-prod \
  --db-parameter-group-name default.postgres16
```
Then run `CREATE EXTENSION IF NOT EXISTS vector;` via psql.

### 3. Security Group
Allow inbound TCP 5432 from your app's IP or security group.

---

## Schema Overview
GharBuddy auto-creates these tables on startup:
| Table | Purpose |
|---|---|
| `Devices` | Device states (status, wattage) |
| `EventLogs` | Sensor event history |
| `EnergyStats` | Cumulative savings tracking |
| `VectorIndex` | RAG rule embeddings (pgvector) |
| `EmbeddingCache` | Titan embedding cache |
