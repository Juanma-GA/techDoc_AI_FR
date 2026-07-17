# REGISTRO DE FUNCIONAMIENTO — Guía de Pruebas en Navegador

**Fecha**: 1 de junio de 2026  
**Propósito**: Documento de trabajo para validación funcional de los 4 POCs  
**Uso**: Seguir esta guía paso a paso cuando se ordenen las pruebas en navegador

---

## INSTRUCCIONES GENERALES

### Prerequisitos

1. ✅ Python 3.11+ instalado
2. ✅ Node.js 20+ + pnpm instalado (opcional para modo preview)
3. ✅ Navegador moderno (Chrome 120+, Firefox 120+, Edge 120+)
4. ✅ Clave API Mistral disponible (obtener en https://console.mistral.ai)

### Estructura de Pruebas

Para cada POC:

1. **Lanzamiento** — Verificar arranque correcto
2. **UI Base** — Navegación, theme toggle, i18n
3. **Funcionalidades Core** — Operaciones principales
4. **Endpoints API** — Verificar respuestas estructuradas
5. **Casos Error** — Validar manejo de errores
6. **Performance** — Medir tiempos de respuesta

### Captura de Evidencias

Por cada sección de pruebas:

- 📸 Screenshot de pantalla principal
- 📋 Copiar output de consola (F12 > Console)
- 📊 Copiar output de Network tab (si aplica)
- ✏️ Anotar observaciones y bugs encontrados

---

## POC 1: FTM (Puerto 8000)

### 1.1 Lanzamiento

```bash
# Desde c:\_Projects\ATEXIS_POCS\apps\ftm
start.bat
```

**Validaciones**:

- [ ] Ventana cmd permanece abierta
- [ ] Mensaje "FTM Agent v4 - Lanzamiento local"
- [ ] "uvicorn app.main:app" se ejecuta
- [ ] URL mostrada: http://127.0.0.1:8000
- [ ] Navegador abre automáticamente

**Output esperado (cmd)**:

```
============================================================
 FTM Agent v4 - Lanzamiento local
============================================================
[info] Python embebido detectado: ...
[info] Backend iniciado en http://127.0.0.1:8000
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**En caso de error**:

- Anotar mensaje exacto
- Verificar puerto ocupado: `netstat -ano | findstr ":8000"`
- Cerrar proceso conflictivo o usar fallback automático

### 1.2 UI Base — Preview HTML (sin Node)

**URL**: http://127.0.0.1:8000/

**Validaciones visuales**:

- [ ] Sidebar izquierda con logo/título "FTM"
- [ ] Topbar con breadcrumb + theme toggle (sun/moon icon)
- [ ] Tabs: Home, Arquitectura, Datos, Configuración, + tabs negocio
- [ ] Footer con versión
- [ ] Paleta dark (fondo #0e1117, texto #e2e8f0)

**Test theme toggle**:

1. Clicar icono sun/moon (top-right)
2. Verificar cambio inmediato a light theme (fondo blanco)
3. Recargar página (F5)
4. **Validar**: Theme persiste (localStorage)

**Test i18n**:

1. Clicar botón "FR" (top-right)
2. Verificar UI en francés
3. Clicar botón "EN"
4. Verificar UI en inglés
5. Recargar página
6. **Validar**: Idioma persiste

**Captura**:

- Screenshot modo dark
- Screenshot modo light
- Console logs (verificar 0 errores)

### 1.3 Pestaña "Home"

**Contenido esperado**:

- [ ] Descripción del POC (3-5 líneas)
- [ ] KPIs principales (proyectos, archivos, anomalías)
- [ ] Valores = 0 (base de datos vacía)

**Test**:

```
# Capturar valores iniciales
Proyectos: 0
Archivos: 0
Anomalías: 0
```

### 1.4 Pestaña "Arquitectura"

**Contenido esperado**:

- [ ] Diagrama de flujo (Upload → Parse → Check → Dashboard)
- [ ] Descripción de cada etapa
- [ ] Tecnologías (FastAPI, SQLite, Mistral, React)

**Test**:

- Verificar legibilidad del texto
- Scroll completo hasta footer

### 1.5 Pestaña "Datos"

**Contenido esperado**:

- [ ] Tabla de estadísticas con contadores
- [ ] Botón "Eliminar todo" (rojo)
- [ ] Botón "Exportar JSON" (si aplica)

**Test reset (ATENCIÓN: destructivo)**:

1. Hacer clic en "Eliminar todo"
2. **Validar**: Modal de confirmación aparece
3. Hacer clic en "Hacer clic de nuevo para confirmar"
4. **Validar**: Contadores vuelven a 0
5. **Validar**: Toast de confirmación "Reset efectuado"

**Captura**:

- Screenshot antes del reset
- Screenshot después del reset

### 1.6 Pestaña "Configuración"

**Contenido esperado**:

- [ ] Formulario config Mistral
  - [ ] Input "Clave API" (tipo password)
  - [ ] Input "Base URL" (default: https://api.mistral.ai)
  - [ ] Input "Modelo chat" (default: mistral-small-latest)
  - [ ] Input "Modelo embed" (default: mistral-embed)
- [ ] Botón "Guardar"
- [ ] Botón "Probar conexión"

**Test guardar clave**:

1. Pegar clave Mistral en input "Clave API"
2. Hacer clic en "Guardar"
3. **Validar**: Toast "Parámetros guardados"
4. Recargar página
5. **Validar**: Clave enmascarada (puntos) pero presente

**Test conexión**:

1. Hacer clic en "Probar conexión"
2. **Validar**: Spinner aparece
3. Esperar 2-5 segundos
4. **Validar**: Lista de modelos aparece O mensaje de error

**Captura**:

- Screenshot formulario (ocultar clave si sensible)
- Screenshot resultado test conexión

### 1.7 Funcionalidades de Negocio FTM

**Upload de documento**:

1. Navegar hacia pestaña de negocio principal
2. Hacer clic en zona dropzone "Soltar un archivo"
3. Seleccionar archivo test (.docx, .pdf, .xlsx)
4. **Validar**: Barra de progreso
5. **Validar**: Documento aparece en lista
6. **Validar**: Contador "Archivos" incrementa

**Análisis**:

1. Hacer clic en botón "Analizar" en documento subido
2. **Validar**: Streaming SSE inicia (spinner)
3. **Validar**: Anomalías aparecen progresivamente
4. **Validar**: Estado "Análisis terminado"

**Dashboard KPI**:

1. Volver a pestaña "Home"
2. **Validar**: KPIs actualizados
3. **Anotar valores**:
   - Proyectos: X
   - Archivos: Y
   - Anomalías: Z

**Captura**:

- Screenshot lista documentos
- Screenshot resultado análisis
- Screenshot KPIs finales

### 1.8 Tests API (curl ou Postman)

**Health check**:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

**Respuesta esperada**:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "db": "connected",
  "llm": "configured" // o "not_configured" si no hay clave
}
```

**Stats admin**:

```bash
curl http://127.0.0.1:8000/api/v1/admin/stats
```

**Formato esperado**:

```json
{
  "projects": 1,
  "files": 3,
  "anomalies": 12,
  "total_size_bytes": 1548327
}
```

**Captura**:

- Copiar JSON responses completos

### 1.9 Tests de Error

**Upload archivo inválido**:

1. Intentar subir .exe o archivo >50MB
2. **Validar**: Mensaje de error claro
3. **Validar**: Sin crash

**Reset sin confirmación**:

1. Hacer clic en "Eliminar todo" una sola vez
2. **Validar**: Acción no se ejecuta
3. **Validar**: Botón pide confirmación

**Desconexión Mistral**:

1. Poner clave API inválida
2. Lanzar análisis
3. **Validar**: Mensaje error "Clave inválida" O "Modelo no disponible"

**Captura**:

- Screenshots mensajes de error

---

## POC 2: DOC-WRITER (Puerto 8002)

### 2.1 Lanzamiento

```bash
# Desde c:\_Projects\ATEXIS_POCS\apps\doc-writer
start.bat
```

**Validaciones**:

- [ ] Puerto 8002 (no 8000)
- [ ] URL: http://127.0.0.1:8002
- [ ] Ventana cmd permanece abierta

### 2.2 UI Base

**Mismos tests que FTM**:

- [ ] Theme toggle dark/light
- [ ] i18n FR/EN
- [ ] Navegación sidebar

### 2.3 Upload de Documentos

**Test multi-archivos**:

1. Subir 3 archivos diferentes (PDF, DOCX, TXT)
2. **Validar**: Los 3 aparecen en lista
3. **Validar**: Parsing automático
4. **Validar**: Contador de chunks generado

**Formatos soportados**:

- PDF ✅
- DOCX ✅
- PPTX ✅
- XLSX ✅
- TXT ✅
- MD ✅

**Captura**:

- Screenshot lista documentos con metadatos (tamaño, chunks)

### 2.4 Generación RAG

**Prompt simple**:

1. Seleccionar documentos subidos
2. Introducir prompt: "Resume los puntos clave"
3. Hacer clic en "Generar"
4. **Validar**: Streaming SSE (texto aparece progresivamente)
5. **Validar**: Citas `[filename.pdf]` presentes
6. **Validar**: Renderizado Markdown (negrita, listas)

**Sesiones**:

1. **Validar**: Sesión creada automáticamente
2. **Validar**: Título auto-generado O modificable
3. Hacer 2ª generación en misma sesión
4. **Validar**: Historial conversacional

**Captura**:

- Screenshot generación en curso (streaming)
- Screenshot resultado final con citas

### 2.5 Export Multi-Formato

**Export Markdown**:

1. Hacer clic en "Descargar .md"
2. **Validar**: Archivo .md descargado
3. Abrir en editor de texto
4. **Validar**: Markdown válido

**Export DOCX**:

1. Hacer clic en "Descargar .docx"
2. Abrir en Word/LibreOffice
3. **Validar**: Formato preservado

**Export PDF**:

1. Hacer clic en "Descargar .pdf"
2. Abrir en lector PDF
3. **Validar**: Contenido legible

**Export PPTX (con template)**:

1. Subir template .pptx con placeholders `{{titulo}}`, `{{contenido}}`
2. Adjuntar template a sesión
3. Generar contenido
4. Hacer clic en "Descargar .pptx"
5. Abrir en PowerPoint
6. **Validar**: Placeholders reemplazados
7. **Validar**: Estilo de template preservado

**Captura**:

- Screenshots archivos exportados abiertos

### 2.6 Tests API

**Endpoints clés**:

```bash
# Documents
curl http://127.0.0.1:8002/api/v1/documents

# Sessions
curl http://127.0.0.1:8002/api/v1/sessions

# Generate (SSE)
curl -N -X POST http://127.0.0.1:8002/api/v1/sessions/{id}/ask \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Test"}'
```

---

## POC 3: PDF-REVIEWER (Puerto 8001)

### 3.1 Lanzamiento

```bash
# Desde c:\_Projects\ATEXIS_POCS\apps\pdf-reviewer
start.bat
```

**Validaciones**:

- [ ] Puerto 8001
- [ ] URL: http://127.0.0.1:8001

### 3.2 Upload PDF

**Test PDF técnico**:

1. Subir PDF técnico (manual, hoja de datos)
2. **Validar**: Parsing exitoso
3. **Validar**: Metadatos extraídos (páginas, tamaño)
4. **Validar**: Capas de texto detectadas

**Test PDF escaneado**:

1. Subir PDF escaneado (imagen raster)
2. **Validar**: Warning "Sin capa de texto"
3. **Validar**: Ninguna sugerencia generada

**Test PDF firmado**:

1. Subir PDF con firma digital
2. **Validar**: Rechazo con código `PDF_HAS_SIGNATURE`

**Captura**:

- Screenshots uploads exitosos y fallidos

### 3.3 Análisis Multi-Normas

**Selección de norma**:

1. Elegir norma: S1000D 5.0
2. Lanzar análisis
3. **Validar**: Sugerencias generadas por categoría
   - [ ] Problemas de terminología
   - [ ] Formato DMC
   - [ ] Problemas de estructura
   - [ ] Conversión de unidades

**Test norma personalizada**:

1. Crear nueva norma "TEST-NORM"
2. Añadir reglas personalizadas (regex)
3. Adjuntar a documento
4. Re-analizar
5. **Validar**: Reglas personalizadas aplicadas

**Captura**:

- Screenshot lista sugerencias por categoría
- Screenshot detalle sugerencia con resaltado en PDF

### 3.4 Aplicación de Sugerencias

**Aceptar**:

1. Hacer clic en "Accept" en sugerencia
2. **Validar**: Estado cambia a "accepted"
3. Hacer clic en "Aplicar todas"
4. **Validar**: Versión PDF incrementa (v0 → v1)
5. Descargar PDF modificado
6. **Validar**: Corrección aplicada en documento

**Editar**:

1. Hacer clic en "Edit" en sugerencia
2. Modificar texto propuesto
3. Guardar
4. Aplicar
5. **Validar**: Texto personalizado insertado

**Rechazar**:

1. Hacer clic en "Reject"
2. **Validar**: Sugerencia oculta (filtrable)

**Rollback**:

1. Después de aplicación, hacer clic en "Rollback to v0"
2. **Validar**: Documento vuelve al estado original
3. **Validar**: EditHistory registra rollback

**Captura**:

- Screenshot antes/después de aplicación
- Screenshot PDF modificado (resaltando cambios)

### 3.5 Visor PDF

**Navegación**:

- [ ] Zoom in/out funciona
- [ ] Scroll de páginas fluido
- [ ] Miniaturas sidebar
- [ ] Búsqueda en PDF

**Resaltados**:

- [ ] Sugerencias resaltadas en amarillo
- [ ] Clic en sugerencia hace scroll a ubicación
- [ ] Bbox preciso (sin desplazamiento)

**Captura**:

- Screenshot visor con resaltados

---

## POC 4: OCR-VISION (Puerto 8003)

### 4.1 Lanzamiento

```bash
# Desde c:\_Projects\ATEXIS_POCS\apps\ocr-vision
start.bat
```

**Validaciones**:

- [ ] Port 8003
- [ ] URL: http://127.0.0.1:8003

### 4.2 Endpoint Test Visión

**Interfaz**:

1. Navegar hacia página principal
2. **Validar**: Formulario de subida imagen/PDF
3. **Validar**: Input prompt personalizado (opcional)

**Test OCR Imagen**:

1. Subir imagen PNG con texto (screenshot, foto documento)
2. Hacer clic en "Analizar"
3. **Validar**: 2 resultados en paralelo:
   - Texto OCR (transcripción bruta)
   - Descripción (francés, 3-5 frases)
4. **Validar**: Si fallo parcial, `errors[]` no vacío

**Test Visión PDF**:

1. Subir PDF con ilustraciones/esquemas
2. **Validar**: Descripción menciona objetos visuales

**Prompt personalizado**:

1. Subir imagen equipo industrial
2. Prompt: "Lista los equipos de seguridad visibles"
3. **Validar**: Descripción enfocada en seguridad

**Captura**:

- Screenshot resultados OCR + descripción
- Copiar respuesta JSON de API

### 4.3 Tests API

**Endpoint principal**:

```bash
curl -X POST http://127.0.0.1:8003/api/v1/vision/test \
  -F "file=@test_image.png" \
  -F "prompt=Describe esta imagen"
```

**Respuesta esperada**:

```json
{
  "ocr_text": "Texto extraído...",
  "description": "Imagen muestra...",
  "errors": []
}
```

**Test error (archivo no imagen)**:

```bash
curl -X POST http://127.0.0.1:8003/api/v1/vision/test \
  -F "file=@test.txt"
```

**Respuesta esperada**: HTTP 400 con código de error

---

## TESTS TRANSVERSALES (Todos los POCs)

### Performance

**Medidas a tomar** (Chrome DevTools):

1. Ouvrir F12 > Network
2. Disable cache
3. Recharger page (Ctrl+Shift+R)
4. **Anotar**:
   - Time to First Byte (TTFB): < 200ms
   - DOMContentLoaded: < 1s
   - Load complete: < 3s
   - Nombre de requêtes: < 50
   - Taille transferée: < 5MB

**Upload gros fichier**:

1. Upload fichier 40-50 MB
2. **Anotar**:
   - Temps upload: X secondes
   - Temps parsing: Y secondes
   - Total: < 2 min acceptable

**Streaming SSE**:

1. Lancer génération longue
2. **Validar**: Tokens arrivent progressivement (pas de buffering)
3. **Anotar**: Latency premier token: < 3s

### Seguridad (Tests básicos)

**Path traversal**:

```bash
# Intentar subida con nombre malicioso
curl -F "file=@test.pdf;filename=../../../etc/passwd" \
  http://127.0.0.1:8000/api/v1/documents
```

**Validar**: Rechazo con error `UPLOAD_PATH_INVALID`

**XSS (preview HTML)**:

1. Inyectar `<script>alert(1)</script>` en input de texto
2. **Validar**: Escapado (sin ejecución de script)

**CORS**:

```bash
curl -H "Origin: http://evil.com" \
  http://127.0.0.1:8000/api/v1/health
```

**Validar**: Sin header `Access-Control-Allow-Origin: *`

### Accesibilidad (a11y)

**Tests manuales**:

- [ ] Navegación por teclado (Tab) funciona
- [ ] Foco visible en todos los elementos interactivos
- [ ] Texto alternativo en imágenes/iconos (si aplica)
- [ ] Contraste de texto suficiente (WCAG AA)
- [ ] Compatible con screen reader (probar con NVDA/JAWS si disponible)

**Auditoría Lighthouse** (Chrome):

1. F12 > Lighthouse
2. Categorías: Performance, Accessibility, Best Practices
3. **Anotar puntuaciones**:
   - Performance: > 80
   - Accessibility: > 90
   - Best Practices: > 90
4. Catégories: Performance, Accessibility, Best Practices
5. **Anotar scores**:
   - Performance: > 80
   - Accessibility: > 90
   - Best Practices: > 90

### Compatibilidad de Navegadores

**Probar en**:

- [ ] Chrome 120+ (referencia)
- [ ] Firefox 120+
- [ ] Edge 120+
- [ ] Safari 17+ (si macOS disponible)

**Validar**:

- Layout idéntico
- Theme toggle funciona
- Sin errores de consola

---

## REGISTRO DE BUGS TROUVÉS

### Template Bug Report

```markdown
**POC**: [ftm | doc-writer | pdf-reviewer | ocr-vision]
**Severidad**: [Crítica | Alta | Media | Baja]
**Tipo**: [Funcional | UI | Performance | Seguridad]

**Descripción**:
[Explicar qué ocurre]

**Pasos para reproducir**:

1. ...
2. ...
3. ...

**Resultado esperado**:
[Qué debería pasar]

**Resultado actual**:
[Qué pasa realmente]

**Evidencias**:

- Screenshot: [adjuntar]
- Console logs: [copiar]
- Network: [copiar si aplica]

**Entorno**:

- OS: Windows 11
- Navegador: Chrome 120.x
- Python: 3.11.x
```

### Bugs Encontrados

_(Completar durante las pruebas)_

---

## CHECKLIST FINAL

### Por cada POC

- [ ] Lanzamiento exitoso
- [ ] UI preview HTML funcional
- [ ] Theme toggle dark/light OK
- [ ] i18n FR/EN OK
- [ ] Upload fichiers OK
- [ ] Funcionalidad core operativa
- [ ] Export/download OK (si aplica)
- [ ] Endpoints API responden correctamente
- [ ] Manejo errores apropiado
- [ ] Performance aceptable (<3s loads)
- [ ] Sin errores de consola críticos

### Global

- [ ] 4 POCs validados individualmente
- [ ] Documento evidencias completo
- [ ] Lista bugs prioritizada
- [ ] Recomendaciones de mejora

---

**FIN DEL REGISTRO**

_Este documento será completado con las evidencias reales durante la sesión de pruebas en navegador ordenada por el usuario._
