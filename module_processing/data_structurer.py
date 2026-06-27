import os
import sys
import json
from dotenv import load_dotenv
from groq import Groq

# --- ARREGLO DE RUTAS ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.config import SessionLocal
from database.models import RawMessage, StructuredJob

# Cargar variables de entorno y conectar con Groq
load_dotenv()
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY)

def process_pending_messages():
    db = SessionLocal()
    
    # Buscar solo los mensajes que están pendientes
    pending_msgs = db.query(RawMessage).filter(RawMessage.status == 'pending').all()

    if not pending_msgs:
        print("[-] No hay mensajes nuevos para procesar.")
        db.close()
        return

    print(f"[*] Se encontraron {len(pending_msgs)} ofertas para limpiar y estructurar.\n")

    for msg in pending_msgs:
        print(f"[*] Procesando mensaje ID: {msg.id}...")
        
        # El Prompt optimizado para la IA
        prompt = f"""
        Eres un asistente experto en recursos humanos y extracción de datos. Tu tarea es extraer la información del texto de la oferta de trabajo provista.
        
        Instrucciones especiales:
        1. **Corrección de Errores:** Corrige cualquier error ortográfico u omisión de letras obvia en el texto (ej. si dice 'Chofe', corrígelo a 'Chofer'; si dice 'hidrogruista', corrígelo a 'Chofer de Hidrogrúa' o similar de forma correcta y profesional).
        2. **Deducción de Ubicación:** Si la ciudad o zona no se menciona de forma explícita con etiquetas como 'Ubicación:', dedúcela del contexto si aparece en otras partes del texto (ej. si la empresa es 'Policlínico Modelo de Cipolletti' o requiere matrícula de 'Río Negro', la ubicación es 'Cipolletti'). Si es imposible deducirla, pon 'No especificada'.
        
        Debes responder ÚNICAMENTE con un JSON válido, sin texto adicional, sin formato markdown, con esta estructura exacta:
        {{
            "puesto": "Nombre del puesto o título profesional corregido y limpio",
            "empresa": "Nombre de la empresa (si no se puede determinar, pon 'No especificada')",
            "ubicacion": "Ciudad y/o provincia deducida o explícita (ej. 'Neuquén', 'Cipolletti', 'Añelo')",
            "requisitos": "Lista de requisitos clave separados por comas",
            "contacto": "Email, teléfono o enlace de postulación"
        }}

        TEXTO DE LA OFERTA:
        {msg.message_text}
        """

        try:
            # Llamada al modelo Llama 3 (Ultra rápido y gratis)
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
                temperature=0.1, # Temperatura baja para que no invente datos
                response_format={"type": "json_object"} # Obligamos a que devuelva solo JSON
            )

            # Extraemos la respuesta y la convertimos de texto a Diccionario Python
            json_response = chat_completion.choices[0].message.content
            data = json.loads(json_response)

            # Guardamos los datos limpios en la nueva tabla
            new_job = StructuredJob(
                raw_message_id=msg.id,
                puesto=data.get('puesto', 'No especificado'),
                empresa=data.get('empresa', 'No especificado'),
                ubicacion=data.get('ubicacion', 'No especificado'),
                requisitos=data.get('requisitos', 'No especificado'),
                contacto=data.get('contacto', 'No especificado')
            )
            db.add(new_job)

            # Marcamos el mensaje original como procesado
            msg.status = 'processed'
            db.commit()
            
            print(f"[+] ¡Éxito! Puesto estructurado: {data.get('puesto')}")
            print(f"    Contacto: {data.get('contacto')}\n")

        except Exception as e:
            print(f"[-] Error al procesar el mensaje ID {msg.id}: {e}")
            db.rollback()

    db.close()
    print("[*] Proceso de limpieza finalizado.")

if __name__ == '__main__':
    process_pending_messages()