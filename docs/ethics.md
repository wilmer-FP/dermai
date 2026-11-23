# Consideraciones éticas — DermAI

Revisión de los riesgos éticos del prototipo y de cómo se abordan en el código. Las limitaciones técnicas están en [limitations.md](limitations.md).

## 1. Uso no diagnóstico

**Riesgo.** Que alguien tome un resultado como diagnóstico y decida (o deje de consultar) a partir de él.

**Medidas:**

| Dónde | Medida |
|---|---|
| Interfaz | Aviso permanente en todas las páginas y aviso específico junto a cada resultado. |
| API | Cada análisis incluye el campo `disclaimer`, y la documentación OpenAPI lo muestra. |
| Imagen procesada | Lleva el aviso **incrustado** en una franja inferior, para que no lo pierda al descargarse o compartirse fuera de la aplicación. |
| Textos | Se habla de «características compatibles con», nunca de diagnósticos. Las clases de la heurística se nombran por su color (negro, amarillo, rojo), no por el tejido. |
| Modelo | Se marca como «prueba de concepto», su confianza como «no calibrada», y se muestran sus métricas junto a sus limitaciones. |

## 2. Privacidad y datos personales

**Riesgo.** Las fotos de lesiones son datos de salud; pueden identificar a una persona por la propia imagen o por sus metadatos.

**Medidas:**

- **Privacidad por diseño.** No se piden ni almacenan datos personales; no hay cuentas de usuario.
- **Metadatos.** Al subir una foto se eliminan su **EXIF** (ubicación GPS, cámara, fecha) y el texto incrustado en PNG. En JPEG se hace sin recomprimir, y la orientación se respeta girando la imagen. Hay pruebas automáticas que lo verifican.
- **Consentimiento.** Antes de subir, el usuario confirma que la imagen no identifica a nadie y que tiene derecho a usarla.
- **Control.** El usuario puede eliminar una imagen con todos sus análisis y archivos.
- **Ámbito local.** Los datos se guardan en el equipo local (`storage/`, PostgreSQL en Docker) y se excluyen del control de versiones.
- **Demo pública en GitHub Pages** ([deployment.md](deployment.md)). El análisis se hace **en el navegador del visitante**: las fotos no se envían a ningún servidor y se guardan solo en ese navegador (IndexedDB). Es la opción más respetuosa con la privacidad.
- **API desplegada con modo demo** (opcional):
  - cada navegador solo ve sus propias imágenes;
  - las imágenes se borran a las 6 horas y con cada reinicio del servidor;
  - hay un límite de uso por IP;
  - la web avisa de no subir fotos identificables.
- **Secretos.** Las credenciales viven en `.env`, que no se versiona; `.env.example` solo contiene valores de ejemplo.

## 3. Datos de entrenamiento y licencias

- **Elección del dataset.** Se revisaron los datasets públicos con máscaras de tejido y se descartaron los de licencia ausente o contradictoria (DFUTissue, ComplexWoundDB, LUTSeg).
- **WoundTissue** (CC BY-NC-SA 4.0):
  - **Atribución** en la ficha del modelo, en la página «Acerca de» y en la documentación.
  - **Uso no comercial**, indicado en esos mismos lugares.
  - **Ni los datos ni los pesos derivados se versionan.**
- **Tests sin imágenes clínicas.** Las pruebas automáticas usan imágenes **sintéticas**.

## 4. Transparencia y honestidad de las métricas

- **Métricas honestas.** Se publica la media **por partición** (0,69 ± 0,18) además de la cifra agregada (0,87), que exagera el rendimiento. También se explica por qué el Dice de necrosis (0,96) no es fiable.
- **Fallos documentados.** Se describen los fracasos conocidos: la heurística en primeros planos y el modelo con piel sana.
- **Reproducibilidad.** Cada entrenamiento guarda configuración, versiones, semilla y hashes de los datos.

## 5. Equidad

- **Sin evaluación.** No se ha evaluado el rendimiento por tono de piel; los métodos basados en color son especialmente sensibles a él.
- **Mitigación parcial.** La heurística usa umbrales **relativos a la piel circundante**, para no marcar como necrótica una piel de fototipo oscuro (comprobado con imágenes sintéticas).
- **Evaluación pendiente.** Una evaluación real requeriría datos anotados y diversos, como la escala de Fitzpatrick o la de Monk.

## 6. Seguridad

- **Validación de archivos.** Se comprueba el contenido real de cada imagen, no solo su extensión. Hay límite de tamaño y protección contra rutas fuera del almacenamiento, y el nombre interno de los archivos nunca se expone.
- **Sin autenticación.** El prototipo no tiene autenticación: la versión local no debe exponerse a internet, y la pública solo se despliega en modo demo. Esto se documenta en la página «Acerca de», en este documento, en las limitaciones y en la guía de despliegue.

## 7. Uso responsable

DermAI sirve para **aprender y experimentar** con procesamiento de imágenes y aprendizaje profundo aplicados a la dermatología. Cualquier uso con pacientes reales requeriría, como mínimo:
- datos amplios con anotación clínica;
- validación prospectiva;
- evaluación de sesgos;
- aprobación ética;
- cumplimiento normativo como producto sanitario (p. ej. el Reglamento (UE) 2017/745).
