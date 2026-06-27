import os
import sys
import hashlib
from dotenv import load_dotenv
from google import genai

# --- ESTO ARREGLA EL ERROR DE RUTAS ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')
# --------------------------------------

from telethon import TelegramClient, events
from database.config import SessionLocal
from database.models import RawMessage

# Cargar variables de entorno
load_dotenv()

API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Configurar el nuevo motor de Visión (SDK oficial actualizado)
client_ai = genai.Client(api_key=GEMINI_API_KEY)

# Detectar tipo de grupo
_target_env = os.getenv('TARGET_GROUP')
try:
    TARGET_GROUP = int(_target_env)
except ValueError:
    TARGET_GROUP = _target_env

client = TelegramClient('mi_sesion_bot', API_ID, API_HASH)

def generate_hash(text):
    clean_text = text.lower().strip()
    return hashlib.sha256(clean_text.encode('utf-8')).hexdigest()

def extract_text_from_image(image_path):
    """Envía la imagen a la IA para extraer el texto usando el nuevo SDK"""
    try:
        # Subir el archivo temporalmente a Google
        sample_file = client_ai.files.upload(file=image_path)
        prompt = "Eres un extractor de datos. Lee esta imagen publicitaria y extrae todo el texto que contenga. Escribe solo el texto extraído de forma clara, sin agregar comentarios tuyos."
        
        # Procesar con el modelo
        response = client_ai.models.generate_content(
            model='gemini-2.5-flash',
            contents=[sample_file, prompt]
        )
        
        # Eliminar la imagen de los servidores de Google por seguridad y espacio
        client_ai.files.delete(name=sample_file.name)
        
        return response.text
    except Exception as e:
        print(f"[-] Error al leer la imagen con IA: {e}")
        return ""

@client.on(events.NewMessage(chats=TARGET_GROUP))
async def handler(event):
    # Generar hash único basado en el ID de mensaje de Telegram y el canal
    msg_hash = generate_hash(f"{TARGET_GROUP}_{event.message.id}")
    
    db = SessionLocal()
    existing_msg = db.query(RawMessage).filter(RawMessage.message_hash == msg_hash).first()
    if existing_msg:
        print(f"[-] Mensaje ID Telegram {event.message.id} ya existe en la base de datos. Ignorado.")
        db.close()
        return

    raw_text = ""
    
    if event.message.message:
        raw_text += event.message.message + "\n\n"

    if event.message.photo:
        print("[*] Imagen detectada. Descargando y leyendo texto (OCR)...")
        temp_path = await event.message.download_media(file="temp_flyer.jpg")
        
        ocr_text = extract_text_from_image(temp_path)
        if ocr_text:
            raw_text += f"--- TEXTO EXTRAÍDO DE LA IMAGEN ---\n{ocr_text}"
            
        if os.path.exists(temp_path):
            os.remove(temp_path)

    if not raw_text.strip():
        db.close()
        return

    new_msg = RawMessage(
        source_name=str(TARGET_GROUP),
        message_text=raw_text.strip(),
        message_hash=msg_hash
    )
    db.add(new_msg)
    db.commit()
    preview_text = raw_text.strip()[:60].replace('\n', ' ')
    print(f"[+] Empleo guardado exitosamente: {preview_text}...")
    db.close()

    # Ejecutar pipeline de estructuración y generación de imágenes en tiempo real
    try:
        print("[*] Iniciando estructuración y generación de imágenes en tiempo real...")
        from module_processing.data_structurer import process_pending_messages
        from module_render.image_generator import generate_images
        
        process_pending_messages()
        generate_images()
        print("[+] Pipeline completado. Listo para aprobación.")
    except Exception as pipe_err:
        print(f"[-] Error en el pipeline en tiempo real: {pipe_err}")

def start_scraping():
    print(f"Iniciando escucha en {TARGET_GROUP}...")
    client.start()
    print("¡Bot de ingesta con Visión Activa escuchando!")
    client.run_until_disconnected()

if __name__ == '__main__':
    start_scraping()