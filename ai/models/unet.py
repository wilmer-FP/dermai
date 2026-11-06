"""U-Net con encoder ResNet-18 (opcionalmente preentrenado en ImageNet)."""

import torch
import torch.nn.functional as F
from torch import nn
from torchvision.models import ResNet18_Weights, resnet18

ARCHITECTURE = "unet-resnet18"


class ConvBlock(nn.Sequential):
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__(
            nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )


class DecoderBlock(nn.Module):
    """Sube la resolución hasta la de la conexión de salto, concatena y aplica dos convoluciones."""

    def __init__(self, in_channels: int, skip_channels: int, out_channels: int) -> None:
        super().__init__()
        self.conv = ConvBlock(in_channels + skip_channels, out_channels)

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        return self.conv(torch.cat([x, skip], dim=1))


class UNetResNet18(nn.Module):
    """Segmentación semántica. Acepta cualquier tamaño de entrada y devuelve logits del mismo tamaño."""

    def __init__(self, num_classes: int, pretrained_encoder: bool = False) -> None:
        super().__init__()
        encoder = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1 if pretrained_encoder else None)
        self.stem = nn.Sequential(encoder.conv1, encoder.bn1, encoder.relu)  # 1/2, 64 canales
        self.pool = encoder.maxpool
        self.layer1 = encoder.layer1  # 1/4, 64
        self.layer2 = encoder.layer2  # 1/8, 128
        self.layer3 = encoder.layer3  # 1/16, 256
        self.layer4 = encoder.layer4  # 1/32, 512
        self.decoder4 = DecoderBlock(512, 256, 256)
        self.decoder3 = DecoderBlock(256, 128, 128)
        self.decoder2 = DecoderBlock(128, 64, 64)
        self.decoder1 = DecoderBlock(64, 64, 32)
        self.head = nn.Conv2d(32, num_classes, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        size = x.shape[-2:]
        s0 = self.stem(x)
        s1 = self.layer1(self.pool(s0))
        s2 = self.layer2(s1)
        s3 = self.layer3(s2)
        s4 = self.layer4(s3)
        d = self.decoder4(s4, s3)
        d = self.decoder3(d, s2)
        d = self.decoder2(d, s1)
        d = self.decoder1(d, s0)
        return F.interpolate(self.head(d), size=size, mode="bilinear", align_corners=False)
