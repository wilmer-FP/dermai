# DermAI experimental model

Copyright (c) 2026 Wilmer Florez. Model weights: CC BY-NC-SA 4.0.
https://creativecommons.org/licenses/by-nc-sa/4.0/

Source checkpoint: `20261105T231652Z_unet-resnet18-woundtissue/model.pt`.
Change: exported trained PyTorch U-Net/ResNet-18 weights to ONNX float32, opset 17.
No retraining, quantization or substitution with generic ImageNet weights.

Training data: WoundTissue public sample (13 images), by M. A. Kabir,
N. Roy, M. E. Hossain, J. Featherston and S. Ahmed.
*Deep Learning for Wound Tissue Segmentation: A Comprehensive Evaluation
using A Novel Dataset*, 2025, https://arxiv.org/abs/2502.10652.
Dataset source and license: https://github.com/akabircs/WoundTissue
(CC BY-NC-SA 4.0). Image copyright remains with original owners.
Dataset images are not included. No endorsement is implied.

Encoder initialized from torchvision ResNet-18 ImageNet weights before
DermAI training; PyTorch/torchvision code is BSD-3-Clause. That software
license does not establish ownership of ImageNet images or grant additional
rights over third-party data. See https://github.com/pytorch/vision#disclaimer-on-datasets-and-pre-trained-models.
ONNX Runtime Web is MIT; OpenCV is Apache-2.0. DermAI source code is MIT;
the separate model license takes precedence for these weights.

Educational and experimental use only. Not clinically validated. Not a
medical diagnostic tool; do not use results for clinical decisions.
Confidence is not calibrated. The tendon class had no training examples.
