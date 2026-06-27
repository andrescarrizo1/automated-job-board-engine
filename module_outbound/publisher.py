import os
import sys
import time
import requests
import json
import unicodedata
from dotenv import load_dotenv

# --- ARREGLO DE RUTAS ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

def strip_accents(text):
    """Elimina acentos y diacríticos de un texto."""
    text = unicodedata.normalize('NFD', text)
    return "".join(c for c in text if unicodedata.category(c) != 'Mn')

def get_dynamic_hashtags(marca_local):
    """Genera hashtags de SEO local basados en el nombre de la marca."""
    clean_brand = marca_local.lower().replace("empleos", "").replace("empleo", "").strip()
    clean_brand = strip_accents(clean_brand)
    brand_tag = clean_brand.replace(" ", "")
    
    if not brand_tag:
        return "#empleo #trabajo #busquedalaboral"
        
    return (
        f"#empleo #trabajo #busquedalaboral "
        f"#{brand_tag} #empleo{brand_tag} #trabajo{brand_tag} "
        f"#{brand_tag}argentina #argentina"
    )

def get_location_id_for_job(job_location):
    """Obtiene el ID de ubicación de Facebook para una localidad específica."""
    if not job_location:
        return os.getenv('FB_LOCATION_ID')
        
    # Normalizar el nombre de la localidad: minúsculas, sin acentos y limpio
    normalized_name = strip_accents(job_location.lower()).strip()
    
    # Intentar cargar locations.json si existe
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, 'locations.json')
    
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                mapping = json.load(f)
            # Limpiar claves del JSON para comparación
            clean_mapping = {strip_accents(k.lower()).strip(): str(v) for k, v in mapping.items()}
            if normalized_name in clean_mapping:
                return clean_mapping[normalized_name]
        except Exception as e:
            print(f"[-] Error al leer locations.json: {e}")
            
    # Si no se encuentra o no existe el archivo, usar el valor por defecto del .env
    return os.getenv('FB_LOCATION_ID')

def get_page_access_token(page_id, user_token):
    """Obtiene el Token de Acceso de la Página de Facebook usando el Token de Usuario."""
    print(f"[*] Obteniendo Token de Acceso de Página para la página {page_id}...")
    url = f"https://graph.facebook.com/v17.0/{page_id}?fields=access_token&access_token={user_token}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        page_token = response.json().get('access_token')
        if not page_token:
            raise ValueError("La API de Facebook no devolvió un access_token para la página.")
        print("[+] Token de página obtenido con éxito.")
        return page_token
    except Exception as e:
        raise RuntimeError(f"Error al obtener token de acceso de la página: {e}")

def generate_seo_caption(job):
    """Genera una descripción optimizada para SEO para el post de redes."""
    marca_local = os.getenv('MARCA_LOCAL', 'EMPLEO LOCAL')
    
    req_bullets = ""
    if job.requisitos and job.requisitos != 'No especificado':
        items = [i.strip() for i in job.requisitos.replace('\n', ',').split(',') if i.strip()]
        for item in items:
            req_bullets += f"  • {item}\n"
    else:
        req_bullets = "  • No especificado por la empresa\n"
        
    hashtags = get_dynamic_hashtags(marca_local)
    
    # Destacamos la ubicación al inicio del caption para mejor SEO local
    caption = (
        f"📍 UBICACIÓN: {job.ubicacion.upper()}, ARGENTINA\n"
        f"💼 OPORTUNIDAD LABORAL en {marca_local.upper()} 💼\n\n"
        f"📌 Puesto: {job.puesto}\n"
        f"🏢 Empresa: {job.empresa}\n"
        f"📍 Ubicación: {job.ubicacion}, Argentina\n\n"
        f"📝 Requisitos y Detalles:\n{req_bullets}\n"
        f"✉️ Contacto para Postulación:\n👉 {job.contacto}\n\n"
        f"📢 ¡Comparte esta oferta o etiqueta en comentarios a quien pueda interesarle! 🙌\n\n"
        f"{hashtags}"
    )
    return caption

def upload_image_to_tmpfiles(image_path):
    """Sube la imagen generada localmente a tmpfiles.org y devuelve la URL directa."""
    print(f"[*] Subiendo imagen {image_path} a tmpfiles.org para URL pública...")
    url = "https://tmpfiles.org/api/v1/upload"
    
    try:
        with open(image_path, 'rb') as f:
            response = requests.post(url, files={'file': f})
            response.raise_for_status()
            res_data = response.json()
            
            view_url = res_data['data']['url']
            direct_url = view_url.replace("https://tmpfiles.org/", "https://tmpfiles.org/dl/")
            print(f"[+] Imagen subida con éxito: {direct_url}")
            return direct_url
    except Exception as e:
        raise RuntimeError(f"Fallo al subir imagen a hosting temporal: {e}")

def publish_job_to_socials(job):
    """Publica el flyer del empleo en Facebook e Instagram (Post y Story)."""
    token = os.getenv('META_ACCESS_TOKEN')
    page_id = os.getenv('FB_PAGE_ID')
    ig_account_id = os.getenv('IG_BUSINESS_ACCOUNT_ID')
    location_id = get_location_id_for_job(job.ubicacion)
    
    if not token or not page_id or not ig_account_id:
        raise ValueError("Falta configurar META_ACCESS_TOKEN, FB_PAGE_ID o IG_BUSINESS_ACCOUNT_ID en el archivo .env")

    # Rutas de las imágenes locales
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    image_path = os.path.join(base_dir, 'module_render', 'exports', f'job_flyer_{job.id}.jpg')
    story_image_path = os.path.join(base_dir, 'module_render', 'exports', f'job_story_{job.id}.jpg')
    
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"No se encuentra la imagen del flyer (feed) en: {image_path}")
    if not os.path.exists(story_image_path):
        raise FileNotFoundError(f"No se encuentra la imagen del flyer (story) en: {story_image_path}")

    # 1. Obtener URLs públicas directas de ambas imágenes
    public_image_url = upload_image_to_tmpfiles(image_path)
    public_story_image_url = upload_image_to_tmpfiles(story_image_path)
    
    # 2. Generar el texto SEO del Post
    caption = generate_seo_caption(job)
    
    results = {}

    # 3. Publicar en Facebook Page (Post Feed) usando el Page Access Token
    try:
        # IMPORTANTE: Para publicar en una página de Facebook sin error 403, 
        # se debe usar el Token de la Página, no el Token de Usuario
        page_token = get_page_access_token(page_id, token)
        
        print("[*] Publicando en muro de Facebook...")
        fb_url = f"https://graph.facebook.com/v17.0/{page_id}/photos"
        fb_payload = {
            'url': public_image_url,
            'message': caption,
            'access_token': page_token
        }
        if location_id:
            fb_payload['place'] = location_id
            
        fb_res = requests.post(fb_url, data=fb_payload)
        
        # Si falla la publicación y habíamos enviado una geolocalización (sea por error 400 o 500), reintentamos de nuevo sin ella
        if fb_res.status_code != 200 and location_id:
            print(f"[!] Falló la publicación con ubicación en Facebook (Status {fb_res.status_code}), reintentando sin geolocalización...")
            fb_payload.pop('place', None)
            fb_res = requests.post(fb_url, data=fb_payload)
            
        fb_res.raise_for_status()
        results['facebook_post_id'] = fb_res.json().get('id')
        print(f"[+] Publicado con éxito en Facebook Feed (ID: {results['facebook_post_id']})")
    except Exception as e:
        print(f"[-] Error al publicar en Facebook: {e}")
        results['facebook_error'] = str(e)

    # 4. Publicar en Instagram Feed (Post Feed)
    try:
        print("[*] Publicando en feed de Instagram...")
        # Paso 1: Crear Contenedor del Item
        ig_media_url = f"https://graph.facebook.com/v17.0/{ig_account_id}/media"
        ig_media_payload = {
            'image_url': public_image_url,
            'caption': caption,
            'access_token': token
        }
        if location_id:
            ig_media_payload['location_id'] = location_id
            
        ig_media_res = requests.post(ig_media_url, data=ig_media_payload)
        
        # Si falla la publicación y habíamos enviado una geolocalización, reintentamos de nuevo sin ella
        if ig_media_res.status_code != 200 and location_id:
            print(f"[!] Falló la publicación con ubicación en Instagram (Status {ig_media_res.status_code}), reintentando sin geolocalización...")
            ig_media_payload.pop('location_id', None)
            ig_media_res = requests.post(ig_media_url, data=ig_media_payload)
            
        ig_media_res.raise_for_status()
        creation_id = ig_media_res.json().get('id')
        
        time.sleep(5)
        
        # Paso 2: Publicar el Contenedor
        ig_pub_url = f"https://graph.facebook.com/v17.0/{ig_account_id}/media_publish"
        ig_pub_payload = {
            'creation_id': creation_id,
            'access_token': token
        }
        ig_pub_res = requests.post(ig_pub_url, data=ig_pub_payload)
        ig_pub_res.raise_for_status()
        results['instagram_post_id'] = ig_pub_res.json().get('id')
        print(f"[+] Publicado con éxito en Instagram Feed (ID: {results['instagram_post_id']})")
    except Exception as e:
        print(f"[-] Error al publicar en Instagram Feed: {e}")
        results['instagram_feed_error'] = str(e)

    # 5. Publicar en Instagram Stories (Historia) usando la imagen vertical de Story
    try:
        print("[*] Publicando en Historias de Instagram...")
        # Paso 1: Crear Contenedor para Story (usando la imagen 9:16)
        ig_story_url = f"https://graph.facebook.com/v17.0/{ig_account_id}/media"
        ig_story_payload = {
            'image_url': public_story_image_url,
            'media_type': 'STORIES',
            'access_token': token
        }
        ig_story_res = requests.post(ig_story_url, data=ig_story_payload)
        ig_story_res.raise_for_status()
        story_creation_id = ig_story_res.json().get('id')
        
        time.sleep(5)
        
        # Paso 2: Publicar la Story
        ig_pub_url = f"https://graph.facebook.com/v17.0/{ig_account_id}/media_publish"
        ig_pub_payload = {
            'creation_id': story_creation_id,
            'access_token': token
        }
        ig_pub_res = requests.post(ig_pub_url, data=ig_pub_payload)
        ig_pub_res.raise_for_status()
        results['instagram_story_id'] = ig_pub_res.json().get('id')
        print(f"[+] Publicado con éxito en Instagram Stories (ID: {results['instagram_story_id']})")
    except Exception as e:
        print(f"[-] Error al publicar en Instagram Stories: {e}")
        results['instagram_story_error'] = str(e)

    has_success = ('facebook_post_id' in results) or ('instagram_post_id' in results) or ('instagram_story_id' in results)
    
    if not has_success:
        errors = {k: v for k, v in results.items() if 'error' in k}
        raise RuntimeError(f"Fallo total de publicación: {errors}")
        
    return results
