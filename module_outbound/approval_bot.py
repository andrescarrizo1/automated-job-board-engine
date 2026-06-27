import os
import sys
import asyncio
from dotenv import load_dotenv

# --- ARREGLO DE RUTAS ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.config import SessionLocal
from database.models import StructuredJob

# Cargar variables de entorno
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')

if not BOT_TOKEN or not ADMIN_ID:
    print("[-] Error: BOT_TOKEN o ADMIN_ID no configurados en el archivo .env")
    sys.exit(1)

try:
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    print("[-] Error: ADMIN_ID debe ser un número entero en el .env.")
    sys.exit(1)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

def escape_tg_html(text):
    """Escapa los caracteres especiales para el parse_mode='HTML' de Telegram."""
    if not text:
        return ""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

async def check_pending_jobs(bot):
    db = SessionLocal()
    try:
        # Buscar ofertas que estén en estado 'pending_review'
        jobs = db.query(StructuredJob).filter(StructuredJob.status == 'pending_review').all()
        if not jobs:
            return
        
        for job in jobs:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            image_path = os.path.join(base_dir, 'module_render', 'exports', f'job_flyer_{job.id}.jpg')
            
            if not os.path.exists(image_path):
                print(f"[-] No se encontró la imagen en {image_path} para el empleo ID {job.id}")
                continue
                
            # Escapar textos para evitar errores de entidad en HTML parse mode
            puesto_esc = escape_tg_html(job.puesto)
            empresa_esc = escape_tg_html(job.empresa)
            ubicacion_esc = escape_tg_html(job.ubicacion)
            contacto_esc = escape_tg_html(job.contacto)
            
            caption = (
                f"📝 <b>Nueva Oferta de Empleo</b>\n\n"
                f"💼 <b>Puesto:</b> {puesto_esc}\n"
                f"🏢 <b>Empresa:</b> {empresa_esc}\n"
                f"📍 <b>Ubicación:</b> {ubicacion_esc}\n"
                f"📞 <b>Contacto:</b> {contacto_esc}\n"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Aprobar", callback_data=f"approve_{job.id}"),
                    InlineKeyboardButton("❌ Rechazar", callback_data=f"reject_{job.id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                with open(image_path, 'rb') as photo:
                    await bot.send_photo(
                        chat_id=ADMIN_ID,
                        photo=photo,
                        caption=caption,
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                # Pasar a 'in_review' para no volver a enviarlo en el próximo ciclo
                job.status = 'in_review'
                db.commit()
                print(f"[+] Oferta ID {job.id} enviada al administrador {ADMIN_ID} para revisión.")
            except Exception as send_err:
                print(f"[-] Error al enviar la foto en Telegram para ID {job.id}: {send_err}")
                
    finally:
        db.close()

async def db_polling_loop(application):
    """Bucle infinito en segundo plano para revisar la base de datos."""
    print("[*] Iniciando bucle de monitoreo de base de datos...")
    while True:
        try:
            await check_pending_jobs(application.bot)
        except Exception as e:
            print(f"[-] Error en el bucle de base de datos: {e}")
        await asyncio.sleep(10) # Escanear cada 10 segundos

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"¡Hola! Soy tu bot de administración de Empleos Locales.\n"
        f"Tu Chat ID es: {chat_id}\n"
        f"Tu ID de Administrador configurado es: {ADMIN_ID}."
    )

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        await update.message.reply_text("Acceso denegado.")
        return
    await update.message.reply_text("Buscando ofertas pendientes de revisión...")
    await check_pending_jobs(context.bot)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not (data.startswith("approve_") or data.startswith("reject_")):
        return
        
    action, job_id_str = data.split("_")
    job_id = int(job_id_str)
    
    db = SessionLocal()
    try:
        job = db.query(StructuredJob).filter(StructuredJob.id == job_id).first()
        if not job:
            await query.edit_message_caption(caption="[-] Error: Oferta no encontrada en la base de datos.")
            return
            
        puesto_esc = escape_tg_html(job.puesto)
        empresa_esc = escape_tg_html(job.empresa)
        ubicacion_esc = escape_tg_html(job.ubicacion)
        contacto_esc = escape_tg_html(job.contacto)

        if action == "reject":
            job.status = "rejected"
            db.commit()
            status_text = "❌ <b>RECHAZADO</b>"
            new_caption = (
                f"{status_text}\n\n"
                f"💼 <b>Puesto:</b> {puesto_esc}\n"
                f"🏢 <b>Empresa:</b> {empresa_esc}\n"
                f"📍 <b>Ubicación:</b> {ubicacion_esc}\n"
                f"📞 <b>Contacto:</b> {contacto_esc}\n"
            )
            await query.edit_message_caption(caption=new_caption, parse_mode='HTML')
            print(f"[+] Oferta ID {job_id} rechazada.")
            return
            
        # Si es aprobación
        # 1. Enviar estado de cargando
        loading_caption = (
            f"⏳ <b>APROBADO</b> - Publicando en Facebook e Instagram...\n\n"
            f"💼 <b>Puesto:</b> {puesto_esc}\n"
            f"🏢 <b>Empresa:</b> {empresa_esc}\n"
        )
        await query.edit_message_caption(caption=loading_caption, parse_mode='HTML')
        
        # 2. Intentar publicar
        from module_outbound.publisher import publish_job_to_socials
        
        try:
            publish_results = publish_job_to_socials(job)
            job.status = "published"
            db.commit()
            status_text = "✅ <b>APROBADO Y PUBLICADO EN REDES</b>"
            
            success_details = ""
            if 'facebook_post_id' in publish_results:
                success_details += "• Facebook Feed: Sí\n"
            if 'instagram_post_id' in publish_results:
                success_details += "• Instagram Feed: Sí\n"
            if 'instagram_story_id' in publish_results:
                success_details += "• Instagram Story: Sí\n"
                
            new_caption = (
                f"{status_text}\n"
                f"{escape_tg_html(success_details)}\n"
                f"💼 <b>Puesto:</b> {puesto_esc}\n"
                f"🏢 <b>Empresa:</b> {empresa_esc}\n"
                f"📍 <b>Ubicación:</b> {ubicacion_esc}\n"
                f"📞 <b>Contacto:</b> {contacto_esc}\n"
            )
        except ValueError as val_err:
            # Falta configuración en .env
            job.status = "approved"
            db.commit()
            status_text = "⚠️ <b>APROBADO LOCALMENTE</b>\n(Falta configurar Meta en .env)"
            new_caption = (
                f"{status_text}\n\n"
                f"💼 <b>Puesto:</b> {puesto_esc}\n"
                f"🏢 <b>Empresa:</b> {empresa_esc}\n"
                f"📍 <b>Ubicación:</b> {ubicacion_esc}\n"
                f"📞 <b>Contacto:</b> {contacto_esc}\n"
            )
            print(f"[-] Aprobado localmente. {val_err}")
        except Exception as pub_err:
            # Error de red/API
            job.status = "approved"
            db.commit()
            status_text = "⚠️ <b>APROBADO</b> (Fallo en API de Meta)"
            new_caption = (
                f"{status_text}\n"
                f"Detalle: {escape_tg_html(str(pub_err)[:120])}...\n\n"
                f"💼 <b>Puesto:</b> {puesto_esc}\n"
                f"🏢 <b>Empresa:</b> {empresa_esc}\n"
                f"📍 <b>Ubicación:</b> {ubicacion_esc}\n"
                f"📞 <b>Contacto:</b> {contacto_esc}\n"
            )
            print(f"[-] Error en publicación de Meta: {pub_err}")
            
        await query.edit_message_caption(caption=new_caption, parse_mode='HTML')
        print(f"[+] Oferta ID {job_id} procesada con éxito.")
        
    except Exception as e:
        print(f"[-] Error en callback: {e}")
        try:
            await query.edit_message_caption(caption=f"[-] Error al procesar la decisión: {escape_tg_html(str(e))}", parse_mode='HTML')
        except:
            pass
    finally:
        db.close()

async def post_init(application):
    """Se ejecuta al iniciar el bot para lanzar la tarea en segundo plano."""
    asyncio.create_task(db_polling_loop(application))

def main():
    print("[*] Iniciando bot de aprobación de Telegram...")
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    print("[+] Bot iniciado con éxito y escuchando eventos!")
    application.run_polling()

if __name__ == '__main__':
    main()
