# 🤖 Automated Job Board Engine (Social Auto-Publisher)

[▶️ Ver Video Demo de la Arquitectura (Próximamente)]

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Meta Graph API](https://img.shields.io/badge/Meta_Graph_API-0468FF?style=for-the-badge&logo=meta&logoColor=white)
![Llama-3](https://img.shields.io/badge/Llama_3-04A3F6?style=for-the-badge&logo=meta&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

Un pipeline ETL (Extract, Transform, Load) end-to-end diseñado para la curaduría y publicación automatizada de contenido en redes sociales. 

Originalmente conceptualizado mediante herramientas No-Code (n8n), tomamos la decisión arquitectónica de migrar el *core* a **Python puro**. Esto nos permitió implementar un sistema transaccional, tolerante a fallos, con un esquema de validación humana (Human-in-the-Loop) y un control fino sobre las APIs de Meta (Facebook/Instagram).

---

## 🏗️ Arquitectura y Flujo de Datos

El sistema está desacoplado en micro-módulos que se comunican a través de una base de datos relacional (SQLite) actuando como única fuente de la verdad, garantizando la idempotencia en cada etapa:

1. **Ingesta en Tiempo Real (`module_ingestion`):** Un scraper asíncrono (`telegram_scraper.py`) escucha canales fuente. Antes de procesar, verifica contra la base de datos el ID único del mensaje para descartar duplicados y ahorrar cuota de API.
2. **Procesamiento de Lenguaje Natural (`module_processing`):** Los mensajes crudos pasan por un LLM (Llama-3 vía Groq). La IA extrae un esquema JSON fuertemente tipado, deduciendo ubicaciones por contexto y corrigiendo errores ortográficos del OCR en tiempo real.
3. **Generación Estática de Assets (`module_render`):** Utilizando un motor headless (`Html2Image`), el sistema inyecta los datos estructurados en plantillas HTML dinámicas para renderizar instantáneamente los flyers y los formatos verticales (Historias 9:16).
4. **Validación Human-in-the-Loop (`module_outbound`):** Un bot administrador en Telegram encola los trabajos generados. El sistema entra en estado `pending_review`, esperando que el operador apruebe o rechace la publicación a través de botones (Callbacks) interactivos.
5. **Publicación y Distribución:** Al aprobar, el sistema inyecta *hashtags* dinámicos (SEO Local) y orquesta la publicación simultánea hacia el Feed de Facebook, el Feed de Instagram y las Historias de Instagram mediante la Meta Graph API.

---

## 🛡️ Estabilidad y Resiliencia (Fault Tolerance)

Para asegurar la estabilidad en producción y lidiar con la inestabilidad de las APIs de terceros, implementamos múltiples capas de resiliencia:

### Graceful Degradation en Meta Graph API
Las APIs de geolocalización de Facebook/Instagram suelen fallar aleatoriamente (Status 400/500) por problemas de indexación de ID de lugares. Nuestro módulo captura estas excepciones de red, descarta dinámicamente el payload de `location_id` y ejecuta un *retry* inmediato, asegurando que el posteo no se pierda por un fallo menor de geolocalización.

```python
# Ejemplo de implementación de Graceful Degradation y Retries
fb_res = requests.post(fb_url, data=fb_payload)

# Si falla la publicación y habíamos enviado una geolocalización (Error 400/500)
# reintentamos inmediatamente de nuevo sin el ID de ubicación.
if fb_res.status_code != 200 and location_id:
    print(f"[!] Falló la publicación con ubicación (Status {fb_res.status_code}), reintentando sin geolocalización...")
    fb_payload.pop('place', None)
    fb_res = requests.post(fb_url, data=fb_payload)
    
fb_res.raise_for_status()
```

### Control de Rate Limits (Evitando 429s)
Para evitar los límites de tasa de las APIs de IA, la base de datos bloquea el procesamiento redundante antes de consultar al LLM. Además, se introdujeron *delays* estratégicos (`time.sleep`) entre la creación de contenedores multimedia de Instagram y su publicación, garantizando que los servidores de Meta terminen de procesar los assets en background.

### Transacciones Atómicas
Las operaciones de lectura/escritura de los estados del trabajo (`pending`, `in_review`, `published`) están gestionadas mediante transacciones en SQLite. Esto previene condiciones de carrera cuando los workers asíncronos y el bot de aprobación de Telegram interactúan con los mismos registros simultáneamente.

---

## 🧠 Justificación Técnica: De n8n a Python Puro

> **¿Por qué migramos la lógica de n8n a Python?**  
> Herramientas visuales como n8n son excelentes para pruebas de concepto (PoC), pero presentan un techo de cristal cuando se requiere manejo de errores granular y orquestación compleja.  

Migrar el orquestador a Python nos otorgó tres ventajas críticas a nivel de ingeniería de software:
1. **Control de Flujo de Red:** Poder implementar bloques de recuperación personalizados (como el patrón de reintento con degradación elegante mencionado anteriormente).
2. **Performance de Rendering:** Integrar librerías nativas como motores headless de Chromium para generar imágenes dinámicas perfectas al píxel, lo cual en n8n requeriría encadenar costosas APIs de SaaS de terceros.
3. **Trazabilidad y Git:** El código puro nos permite versionado semántico estricto, pruebas y facilidad para inyectar logs, transformando un "flujo de cajitas" en infraestructura sólida, predecible y auditable.