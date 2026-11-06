# Alcance del proyecto — DermAI

## 1. Propósito

DermAI es un prototipo de investigación experimental y de portafolio. Su objetivo es explorar técnicas de procesamiento de imágenes e inteligencia artificial aplicadas al estudio de características visuales de lesiones cutáneas, con énfasis en el tejido necrótico. **No es un dispositivo médico ni una herramienta de diagnóstico.**

## 2. Alcance del MVP

### Funcionalidades incluidas
- **Carga de imágenes:** subir fotografías de lesiones cutáneas (JPG/PNG) desde la interfaz web, con validación de formato y tamaño.
- **Almacenamiento:** guardar las imágenes en almacenamiento local y sus metadatos en PostgreSQL.
- **Preprocesamiento:** pipeline básico con OpenCV (redimensionado, normalización, reducción de ruido, extracción de la región de interés).
- **Análisis experimental:** ejecución de un modelo PyTorch experimental que genere una salida orientativa (por ejemplo, mapa o porcentaje estimado de regiones con características visuales compatibles con tejido necrótico).
- **Visualización de resultados:** mostrar la imagen original, la imagen procesada y la salida del modelo.
- **Historial básico:** listar los análisis realizados.
- **Aviso permanente** de uso educativo y no diagnóstico en la interfaz.
- **Documentación técnica** y pruebas básicas del backend y del módulo de IA.

### Requisitos no funcionales del MVP
- Código modular y documentado.
- Configuración mediante variables de entorno.
- Ejecución local en entorno de desarrollo.
- Sin almacenamiento de datos personales identificables.

## 3. Fuera del alcance de la primera versión
- Diagnóstico médico, recomendaciones clínicas o de tratamiento.
- Validación clínica o certificación como dispositivo médico.
- Gestión de pacientes, historias clínicas o integración con sistemas hospitalarios (HL7/FHIR, PACS).
- Autenticación avanzada, roles y gestión multiusuario.
- Despliegue en producción, alta disponibilidad o escalado.
- Contenedorización de la aplicación completa (Docker) y orquestación. Solo la base de datos de desarrollo usa Docker.
- Aplicación móvil o captura directa desde cámara.
- Entrenamiento distribuido o en GPU en la nube.
- Clasificación de múltiples patologías dermatológicas.
- Almacenamiento en la nube (S3 u otros).
- Cumplimiento normativo formal (HIPAA, RGPD aplicado a datos clínicos reales).

## 4. Supuestos y restricciones
- Se usarán únicamente datasets públicos con licencia compatible o imágenes con consentimiento explícito.
- Los resultados del modelo tienen carácter exploratorio y pueden ser imprecisos.
- El proyecto se desarrolla de forma incremental según la [hoja de ruta](development-roadmap.md).

## 5. Criterios de éxito del MVP
- Flujo completo funcional: carga → preprocesamiento → análisis → visualización.
- Arquitectura modular documentada y coherente con [architecture.md](architecture.md).
- Métricas de evaluación del modelo experimental registradas y reproducibles.

## 6. Estado al cierre (Etapa 8)

| Criterio o funcionalidad | Estado | Evidencia |
|---|---|---|
| Flujo carga → preprocesamiento → análisis → visualización | ✅ | Interfaz web y API; prueba de integración del flujo completo con PostgreSQL |
| Preprocesamiento con OpenCV | ✅ | `ai/preprocessing`, [image-processing.md](image-processing.md) |
| Modelo experimental de PyTorch | ✅ Prueba de concepto | `ai/models`, [model.md](model.md); entrenado con solo 13 imágenes públicas |
| Imagen original, procesada y salida del modelo | ✅ | Página de resultado con selector de imagen y leyenda |
| Historial | ✅ | Paginado y con filtro por estado |
| Aviso permanente de uso no diagnóstico | ✅ | Interfaz, API e imagen procesada; ver [ethics.md](ethics.md) |
| Sin datos personales identificables | ✅ Parcial | No se piden datos y se eliminan los metadatos de las fotos; el contenido de la imagen depende del usuario |
| Métricas registradas y reproducibles | ✅ | `ai/experiments/train.py`: configuración, entorno, hashes y validación cruzada |
| Documentación técnica y pruebas | ✅ | 194 pruebas automáticas, cobertura del 97 %; ver [testing.md](testing.md) |
