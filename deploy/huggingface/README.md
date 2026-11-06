---
title: DermAI API
emoji: 🩺
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: cc-by-nc-sa-4.0
short_description: API experimental de lesiones cutáneas (no diagnóstico)
---

# DermAI API (demo)

API del prototipo educativo **DermAI**, que analiza fotografías de lesiones cutáneas con especial interés en el tejido necrótico. Es un proyecto de portafolio que combina Ingeniería de Sistemas y Medicina.

> ⚠️ **No es una herramienta de diagnóstico médico.** Es un prototipo experimental y educativo, sin validación clínica. Sus resultados no deben usarse para tomar decisiones clínicas.

- **Interfaz web:** <https://wilmer-fp.github.io/dermai/>
- **Código fuente:** <https://github.com/wilmer-FP/dermai>
- **Documentación de la API:** `/docs` en este Space

## Cómo funciona la demo

- **Métodos de análisis:** heurística de OpenCV (clasificación por color) o modelo experimental de PyTorch (U-Net con encoder ResNet-18).
- **Privacidad:**
  - cada visitante solo ve sus propias imágenes, mediante un identificador anónimo de sesión;
  - al subir una foto se eliminan sus metadatos (EXIF, GPS);
  - las imágenes se borran a las 6 horas, y todos los datos se pierden al reiniciarse el Space.
- **Límite de uso:** 30 subidas y análisis por hora y dirección IP.
- **Arranque:** el Space duerme cuando nadie lo usa, y la primera petición puede tardar 1–2 minutos.

## Modelo y licencia

El modelo es una **prueba de concepto** entrenada con solo 13 imágenes de la muestra pública del dataset **WoundTissue**:

> M. A. Kabir, N. Roy, M. E. Hossain, J. Featherston y S. Ahmed. *Deep Learning for Wound Tissue Segmentation: A Comprehensive Evaluation using A Novel Dataset*. arXiv:2502.10652, 2025. <https://github.com/akabircs/WoundTissue>

- **Licencia:** el dataset se publica con licencia **CC BY-NC-SA 4.0**. Los pesos del modelo (`model/model.pt`), como obra derivada, se distribuyen con la misma licencia y **solo para uso no comercial**.
- **Rendimiento:** el Dice sin fondo es de 0,69 ± 0,18 por partición en validación cruzada, una cifra **no representativa** con tan pocos datos.
- **Limitaciones:** el modelo falla con fotos que incluyen piel sana, y su confianza no está calibrada. Detalle en `model/model_card.md`.
