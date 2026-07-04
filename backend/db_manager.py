import psycopg2
import json
import random
import config

# 1. Configurazioni in alto
DB_CONFIG = config.DB_CONFIG

# 2. DEFINIZIONE DELLA FUNZIONE (Deve stare qui, SOPRA le altre)
def get_connection():
    return psycopg2.connect(**DB_CONFIG)

# 3. Funzioni che chiamano get_connection()
def init_db():
    # Qui inseriamo tutte le colonne reali, senza puntini
    query = '''CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                sender VARCHAR(255) NOT NULL,
                code VARCHAR(10),
                file_paths JSONB DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );'''
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            conn.commit()

def register_or_append_file(sender, file_path):
    """
    Gestisce l'inserimento o l'aggiornamento automatico.
    Restituisce il codice associato all'utente.
    """
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. Verifica se il numero è già "registrato" (ha un ordine aperto)
    # Ordiniamo per ID decrescente per prendere l'ultimo inserito
    cur.execute("SELECT id, code FROM orders WHERE sender = %s ORDER BY id DESC LIMIT 1", (sender,))
    row = cur.fetchone()
    
    code = None
    
    if row:
        # CASO ESISTE: Aggiorna l'array JSON
        order_id = row[0]
        code = row[1] # Manteniamo lo stesso codice
        
        cur.execute("""
            UPDATE orders 
            SET file_paths = file_paths || %s::jsonb
            WHERE id = %s
        """, (json.dumps([file_path]), order_id))
        
        print(f"--- [DB] File aggiunto all'ordine esistente {order_id} ---")
        
    else:
        # CASO NON ESISTE: Crea nuova entry
        code = str(random.randint(1000, 9999))
        
        cur.execute("""
            INSERT INTO orders (sender, code, file_paths) 
            VALUES (%s, %s, %s)
        """, (sender, code, json.dumps([file_path])))
        
        print(f"--- [DB] Nuova entry creata con codice {code} ---")
    
    conn.commit()
    cur.close()
    conn.close()
    
    return code