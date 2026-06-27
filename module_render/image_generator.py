import os
import sys
from html2image import Html2Image
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# --- ARREGLO DE RUTAS ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.config import SessionLocal
from database.models import StructuredJob

# Configurar el generador de imágenes (1000x1000 px para Instagram)
hti = Html2Image(size=(1000, 1000))

# Rutas de los archivos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, 'template.html')
TEMPLATE_STORY_PATH = os.path.join(BASE_DIR, 'template_story.html')
OUTPUT_DIR = os.path.join(BASE_DIR, 'exports')

# Crear carpeta de exportación si no existe
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def generate_images():
    db = SessionLocal()
    
    # Buscar ofertas estructuradas que estén en estado 'pending'
    jobs = db.query(StructuredJob).filter(StructuredJob.status == 'pending').all()
    
    if not jobs:
        print("[-] No hay ofertas estructuradas pendientes de imagen en la base de datos.")
        db.close()
        return

    # Leer el contenido del molde HTML (Feed)
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as file:
        html_template = file.read()

    # Leer el contenido del molde HTML (Story)
    with open(TEMPLATE_STORY_PATH, 'r', encoding='utf-8') as file:
        html_story_template = file.read()

    marca_local = os.getenv('MARCA_LOCAL', 'EMPLEO LOCAL')

    for job in jobs:
        # Ignorar si la IA determinó que no era una oferta válida (No especificado)
        if job.puesto == 'No especificado':
            print(f"[*] Ignorando ID {job.id} (Puesto no válido/Promoción genérica).")
            job.status = 'rejected'
            db.commit()
            continue
            
        print(f"[*] Generando imágenes (Feed + Story) para: {job.puesto[:30]}...")
        
        # 1. Generar la imagen para el Feed (Cuadrada)
        job_html = html_template.replace('{{puesto}}', str(job.puesto)) \
                                .replace('{{empresa}}', str(job.empresa)) \
                                .replace('{{ubicacion}}', str(job.ubicacion)) \
                                .replace('{{requisitos}}', str(job.requisitos)) \
                                .replace('{{contacto}}', str(job.contacto)) \
                                .replace('{{marca_local}}', str(marca_local))
        
        output_filename = f"job_flyer_{job.id}.jpg"
        hti.output_path = OUTPUT_DIR
        hti.size = (1000, 1000)
        hti.screenshot(html_str=job_html, save_as=output_filename)
        
        # 2. Generar la imagen para Story (Vertical 9:16)
        job_story_html = html_story_template.replace('{{puesto}}', str(job.puesto)) \
                                            .replace('{{empresa}}', str(job.empresa)) \
                                            .replace('{{ubicacion}}', str(job.ubicacion)) \
                                            .replace('{{requisitos}}', str(job.requisitos)) \
                                            .replace('{{contacto}}', str(job.contacto)) \
                                            .replace('{{marca_local}}', str(marca_local))
        
        output_story_filename = f"job_story_{job.id}.jpg"
        hti.size = (1080, 1920)
        hti.screenshot(html_str=job_story_html, save_as=output_story_filename)
        
        # Actualizar el estado en la base de datos a 'pending_review'
        job.status = 'pending_review'
        db.commit()
        
        print(f"[+] ¡Imágenes generadas con éxito para ID {job.id} (flyer + story)!")

    db.close()
    print("[*] Generación de imágenes finalizada.")

if __name__ == '__main__':
    generate_images()
    
    