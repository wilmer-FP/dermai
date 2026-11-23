# Ficha del modelo: unet-resnet18-woundtissue v0.1.0

> Modelo **experimental** con fines educativos. No es una herramienta de diagnóstico médico.

- Ejecución: `20261105T231652Z_unet-resnet18-woundtissue`
- Arquitectura: unet-resnet18 (encoder preentrenado en ImageNet)
- Datos: WoundTissue, muestra pública de 13 imágenes (CC BY-NC-SA 4.0, uso no comercial)
- Imágenes por clase: background 13, granulation 8, slough 5, necrosis 2, maceration 5, tendon 0, bone 1
- Entrada: lado mayor 256 px · 40 épocas · semilla 42

## Validación cruzada (Dice por grupo de tejido)

| Grupo | Modelo | Heurística OpenCV |
|---|---|---|
| granulation | 0.954 | 0.000 |
| slough | 0.817 | 0.551 |
| necrotic | 0.958 | 0.142 |
| other | 0.754 | 0.102 |

- Dice medio sin fondo por partición: 0.694 ± 0.179 (de 0.825, 0.584, 0.586, 0.496, 0.979)
- Dice medio sin fondo agregado (todas las particiones juntas): modelo 0.870, heurística 0.199
- Error absoluto medio de la proporción necrótica: modelo 0.017, heurística 0.139

## Limitaciones

- Con 13 imágenes, las métricas tienen una varianza enorme y no son representativas.
- La necrosis aparece en muy pocas imágenes de la muestra; su segmentación no es fiable.
- Las imágenes del dataset son recortes ajustados de heridas; fotos con mucha piel o fondo quedan fuera de su distribución.
- La confianza que devuelve la inferencia no está calibrada.
