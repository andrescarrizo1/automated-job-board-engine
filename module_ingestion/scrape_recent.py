import os
import sys
import hashlib
from dotenv import load_dotenv
from google import genai

# --- ARREGLO DE RUTAS ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from telethon import TelegramClient
from database.config import SessionLocal
from database.models import RawMessage

# Cargar variables de entorno
load_dotenv()

API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
TARGET_GROUP = os.getenv('TARGET_GROUP', '@liofernandezavisos')

# Configurar el nuevo motor de Visión
client_ai = genai.Client(api_key=GEMINI_API_KEY)

client = TelegramClient('mi_sesion_bot', API_ID, API_HASH)

def generate_hash(text):
    clean_text = text.lower().strip()
    return hashlib.sha256(clean_text.encode('utf-8')).hexdigest()

def extract_text_from_image(image_path):
    """Envía la imagen a la IA para extraer el texto usando el nuevo SDK"""
    try:
        sample_file = client_ai.files.upload(file=image_path)
        prompt = "Eres un extractor de datos. Lee esta imagen publicitaria y extrae todo el texto que contenga. Escribe solo el texto extraído de forma clara, sin agregar comentarios tuyos."
        
        response = client_ai.models.generate_content(
            model='gemini-2.5-flash',
            contents=[sample_file, prompt]
        )
        
        client_ai.files.delete(name=sample_file.name)
        return response.text
    except Exception as e:
        print(f"[-] Error al leer la imagen con IA: {e}")
        return ""

async def main():
    print(f"[*] Conectando a Telegram para extraer mensajes recientes de {TARGET_GROUP}...")
    await client.start()
    
    # Obtener los últimos 15 mensajes del grupo/canal
    print("[*] Obteniendo los últimos 15 mensajes...")
    messages = []
    async for message in client.iter_messages(TARGET_GROUP, limit=15):
        messages.append(message)
        
    print(f"[+] Se recuperaron {len(messages)} mensajes. Procesando...")
    
    db = SessionLocal()
    new_jobs_count = 0
    
    for i, msg in enumerate(messages):
        # Generar hash único basado en el ID de mensaje de Telegram y el canal
        msg_hash = generate_hash(f"{TARGET_GROUP}_{msg.id}")
        
        # Verificar si ya existe en la base de datos antes de hacer nada más
        existing_msg = db.query(RawMessage).filter(RawMessage.message_hash == msg_hash).first()
        if existing_msg:
            print(f"[-] Mensaje {i+1} (ID Telegram: {msg.id}) ya existe en la base de datos. Saltando...")
            continue
            
        raw_text = ""
        
        if msg.message:
            raw_text += msg.message + "\n\n"
            
        if msg.photo:
            print(f"[*] Mensaje {i+1}: Imagen detectada. Descargando y aplicando OCR...")
            temp_path = await msg.download_media(file=f"temp_flyer_{msg.id}.jpg")
            
            ocr_text = extract_text_from_image(temp_path)
            if ocr_text:
                raw_text += f"--- TEXTO EXTRAÍDO DE LA IMAGEN ---\n{ocr_text}"
                
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
        if not raw_text.strip():
            continue
            
        new_msg = RawMessage(
            source_name=str(TARGET_GROUP),
            message_text=raw_text.strip(),
            message_hash=msg_hash,
            status='pending'
        )
        db.add(new_msg)
        db.commit()
        new_jobs_count += 1
        preview = raw_text.strip()[:60].replace('\n', ' ')
        print(f"[+] Nuevo mensaje guardado (ID DB: {new_msg.id}): {preview}...")
            
    db.close()
    print(f"\n[*] Proceso finalizado. Se agregaron {new_jobs_count} nuevas ofertas en estado 'pending'.")

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())
