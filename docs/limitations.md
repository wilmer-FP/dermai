# Limitaciones conocidas — DermAI

DermAI es un **prototipo educativo y experimental**. Este documento reúne sus limitaciones para que nadie atribuya a sus resultados una fiabilidad que no tienen.

## 1. Clínicas

- **No diagnostica.** No ha sido validado con profesionales ni con pacientes, y no sustituye la valoración clínica.
- **No hay referencia clínica.** Los resultados no se han comparado con evaluaciones de expertos sobre imágenes reales, salvo las 13 imágenes anotadas del dataset público.
- **Color no es tejido.** «Compatible con tejido necrótico» significa «de color negro o marrón oscuro» en la heurística, o «parecido a lo que el modelo vio etiquetado como necrosis». Sombras, costras, hematomas, tatuajes, pelo o lesiones pigmentadas pueden producir falsos positivos.

## 2. Heurística de OpenCV

- **Encuadre.** Supone una lesión aproximadamente centrada y rodeada de piel. En primeros planos, donde la herida llena el encuadre, la «piel de referencia» es la propia herida. Medido en la Etapa 7: Dice de granulación 0,00 en el dataset WoundTissue.
- **Umbrales fijos.** Se eligieron con imágenes sintéticas y una sola foto real; no están validados.
- **Variaciones de captura.** Depende de la iluminación y la cámara. La constancia de color parcial reduce, pero no elimina, ese efecto.
- **Clase roja ambigua.** No distingue granulación de eritema o inflamación.

## 3. Modelo experimental

- **Datos insuficientes.** Se entrenó con **13 imágenes**; solo 2 tienen necrosis, y el hueso aparece en una.
  - Dice sin fondo por partición: 0,69 ± 0,18.
  - El Dice de necrosis (0,96) está inflado, porque en esas 2 imágenes la necrosis ocupa casi todo el encuadre.
- **Fuera de su distribución.** El dataset solo contiene recortes de herida. Con fotos que incluyen piel sana, el modelo clasifica la piel como tejido de herida; se comprobó con una imagen sintética.
- **Confianza no calibrada.** Puede ser alta (87 % en la prueba anterior) aunque el resultado sea incorrecto.
- **Licencia.** Solo puede usarse con fines no comerciales (CC BY-NC-SA 4.0 de WoundTissue).

## 4. Sesgos

- **Sin evaluación de sesgos.** No se ha medido el rendimiento por tono de piel, edad, localización anatómica, cámara o iluminación.
- **Mitigación parcial.** La heurística exige que el tejido «necrótico» sea más oscuro que la piel circundante, para no marcar entera una piel de fototipo oscuro. Hay pruebas sintéticas de esa regla, pero no una evaluación con imágenes reales.

## 5. Técnicas y de seguridad

- **Sin autenticación ni control de acceso.** La versión local no debe exponerse a internet.
  - La demo pública usa el modo demo ([deployment.md](deployment.md)). El identificador anónimo de sesión separa a los visitantes, pero no es una credencial: quien lo copiara vería esas imágenes hasta que se borren (6 h).
  - El límite de peticiones vive en memoria, en un solo proceso.
- **Procesamiento síncrono.** Los análisis se procesan dentro de la petición, en unos 50–300 ms. No hay cola de trabajos ni límites de uso.
- **Almacenamiento local.** Las imágenes se guardan en disco local sin cifrar y sin política de retención automática; el usuario las borra a mano.
- **Entorno de desarrollo.** La base de datos de desarrollo usa un usuario con privilegios de superusuario (comportamiento de la imagen oficial de PostgreSQL); no es apto para entornos compartidos.
- **Plataforma.** Solo se ha probado en Windows 11 con Python 3.12, Node.js 24 y Docker Desktop.

- **Demo pública (modo navegador):**
  - Solo ofrece la heurística; el modelo de PyTorch requiere el backend.
  - Los datos viven en IndexedDB del navegador: se pierden si el visitante borra los datos del sitio y no se comparten entre dispositivos.
  - La primera vez descarga unos 4 MB de OpenCV.js.

## 6. Privacidad

- Se eliminan los metadatos de las fotos (EXIF, GPS, texto en PNG), pero **el contenido de la imagen** puede identificar a una persona: rostro, tatuajes, documentos o fondo reconocible. La aplicación pide confirmación, pero no lo comprueba.
- No se piden datos personales ni se registran en los logs; sí se guarda el nombre original del archivo, que el usuario podría usar para identificar a alguien.

Ver también [ethics.md](ethics.md), [image-processing.md](image-processing.md) y [model.md](model.md).
