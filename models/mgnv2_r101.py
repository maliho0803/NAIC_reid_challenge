#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time    : 2019/11/24 9:33 上午
# @author  : wuh-xmu
# @FileName: mgnv2.py
# @Software: PyCharm


import copy
import gc
import torch
from torch import nn
import torch.nn.functional as F
from torchvision.models import resnet50

from .resnet_ibn_a import resnet50_ibn_a, resnet101_ibn_a
from .kaiming_init import weights_init_classifier, weights_init_kaiming
from .attention import CAM_Module, PAM_Module

_all__ = ['mgnv2_resnet101_512']


def l2_norm(x, axis=-1):
    """Normalizing to unit length along the specified dimension.
    Args:
        x (torch.Tensor): feature matrix with shape (batch_size, feat_dim).
    Returns:
        x (torch.Tensor): same shape as input
    """
    x = 1. * x / (torch.norm(x, 2, axis, keepdim=True).expand_as(x) + 1e-12)
    return x


class MGNv2(nn.Module):
    def __init__(self, resnet, num_classes, local_dim=512):
        super(MGNv2, self).__init__()

        self.backbone = nn.Sequential(
            resnet.conv1,
            resnet.bn1,
            resnet.relu,
            resnet.maxpool,
            resnet.layer1,
            resnet.layer2,
            resnet.layer3,
        )

        downsample_part = copy.deepcopy(resnet.layer4)
        downsample_part[0].downsample[0].stride = (2, 2)
        downsample_part[0].conv2.stride = (2, 2)

        self.p1 = nn.Sequential(copy.deepcopy(downsample_part))
        self.p2 = nn.Sequential(copy.deepcopy(resnet.layer4))
        self.p3 = nn.Sequential(copy.deepcopy(resnet.layer4))

        # pool2d = nn.AdaptiveMaxPool2d

        self.gap = nn.AdaptiveAvgPool2d((1, 1))
        self.maxpool_zp2 = nn.AdaptiveMaxPool2d((2, 1))
        self.maxpool_zp3 = nn.AdaptiveMaxPool2d((3, 1))

        res_conv5_reduction = nn.Sequential(
            nn.Conv2d(2048, local_dim, 1, bias=False),
            nn.BatchNorm2d(local_dim),
            nn.ReLU(True)
        )

        self._init_reduction(res_conv5_reduction)

        self.res_conv5_reduction_0 = copy.deepcopy(res_conv5_reduction)
        self.res_conv5_reduction_1 = copy.deepcopy(res_conv5_reduction)
        self.res_conv5_reduction_2 = copy.deepcopy(res_conv5_reduction)
        self.res_conv5_reduction_3 = copy.deepcopy(res_conv5_reduction)
        self.res_conv5_reduction_4 = copy.deepcopy(res_conv5_reduction)
        self.res_conv5_reduction_5 = copy.deepcopy(res_conv5_reduction)
        self.res_conv5_reduction_6 = copy.deepcopy(res_conv5_reduction)
        self.res_conv5_reduction_7 = copy.deepcopy(res_conv5_reduction)

        res_conv5_global_bn = nn.BatchNorm1d(local_dim)
        res_conv5_global_bn.bias.requires_grad_(False)
        res_conv5_global_bn.apply(weights_init_kaiming)

        res_conv5_local_bn = nn.BatchNorm1d(local_dim)
        res_conv5_local_bn.bias.requires_grad_(False)
        res_conv5_local_bn.apply(weights_init_kaiming)

        self.res_conv5_bn_0 = copy.deepcopy(res_conv5_global_bn)
        self.res_conv5_bn_1 = copy.deepcopy(res_conv5_global_bn)
        self.res_conv5_bn_2 = copy.deepcopy(res_conv5_global_bn)
        self.res_conv5_bn_3 = copy.deepcopy(res_conv5_local_bn)
        self.res_conv5_bn_4 = copy.deepcopy(res_conv5_local_bn)
        self.res_conv5_bn_5 = copy.deepcopy(res_conv5_local_bn)
        self.res_conv5_bn_6 = copy.deepcopy(res_conv5_local_bn)
        self.res_conv5_bn_7 = copy.deepcopy(res_conv5_local_bn)

        res_conv5_global_fc = nn.Linear(local_dim, num_classes, bias=False)
        res_conv5_global_fc.apply(weights_init_classifier)

        res_conv5_local_fc = nn.Linear(local_dim, num_classes, bias=False)
        res_conv5_local_fc.apply(weights_init_classifier)

        self.res_conv5_fc_0 = copy.deepcopy(res_conv5_global_fc)
        self.res_conv5_fc_1 = copy.deepcopy(res_conv5_global_fc)
        self.res_conv5_fc_2 = copy.deepcopy(res_conv5_global_fc)
        self.res_conv5_fc_3 = copy.deepcopy(res_conv5_local_fc)
        self.res_conv5_fc_4 = copy.deepcopy(res_conv5_local_fc)
        self.res_conv5_fc_5 = copy.deepcopy(res_conv5_local_fc)
        self.res_conv5_fc_6 = copy.deepcopy(res_conv5_local_fc)
        self.res_conv5_fc_7 = copy.deepcopy(res_conv5_local_fc)

        del resnet, res_conv5_global_fc, res_conv5_local_fc
        del res_conv5_global_bn, res_conv5_local_bn, res_conv5_reduction
        gc.collect()

    @staticmethod
    def _init_reduction(reduction):
        # conv
        nn.init.kaiming_normal_(reduction[0].weight, mode='fan_in')
        # nn.init.constant_(reduction[0].bias, 0.)

        # bn
        nn.init.normal_(reduction[1].weight, mean=1., std=0.02)
        nn.init.constant_(reduction[1].bias, 0.)

    def forward(self, x):
        # x = self.input_norm(x)
        x = self.backbone(x)
        p1 = self.p1(x)
        p2 = self.p2(x)
        p3 = self.p3(x)

        global_feature_p1 = self.gap(p1)
        global_feature_p2 = self.gap(p2)
        global_feature_p3 = self.gap(p3)

        local_features_p2 = self.maxpool_zp2(p2)
        local_feature_0_p2 = local_features_p2[:, :, 0:1, :]
        local_feature_1_p2 = local_features_p2[:, :, 1:2, :]
        local_features_p3 = self.maxpool_zp3(p3)
        local_feature_0_p3 = local_features_p3[:, :, 0:1, :]
        local_feature_1_p3 = local_features_p3[:, :, 1:2, :]
        local_feature_2_p3 = local_features_p3[:, :, 2:3, :]

        global_triplet_feature_p1 = self.res_conv5_reduction_0(global_feature_p1).flatten(1)
        global_triplet_feature_p2 = self.res_conv5_reduction_1(global_feature_p2).flatten(1)
        global_triplet_feature_p3 = self.res_conv5_reduction_2(global_feature_p3).flatten(1)

        local_softmax_feature_0_p2 = self.res_conv5_reduction_3(local_feature_0_p2).flatten(1)
        local_softmax_feature_1_p2 = self.res_conv5_reduction_4(local_feature_1_p2).flatten(1)
        local_softmax_feature_0_p3 = self.res_conv5_reduction_5(local_feature_0_p3).flatten(1)
        local_softmax_feature_1_p3 = self.res_conv5_reduction_6(local_feature_1_p3).flatten(1)
        local_softmax_feature_2_p3 = self.res_conv5_reduction_7(local_feature_2_p3).flatten(1)

        global_softmax_feature_p1 = self.res_conv5_bn_0(global_triplet_feature_p1)
        global_softmax_feature_p2 = self.res_conv5_bn_1(global_triplet_feature_p2)
        global_softmax_feature_p3 = self.res_conv5_bn_2(global_triplet_feature_p3)

        local_softmax_feature_0_p2 = self.res_conv5_bn_3(local_softmax_feature_0_p2)
        local_softmax_feature_1_p2 = self.res_conv5_bn_4(local_softmax_feature_1_p2)
        local_softmax_feature_0_p3 = self.res_conv5_bn_5(local_softmax_feature_0_p3)
        local_softmax_feature_1_p3 = self.res_conv5_bn_6(local_softmax_feature_1_p3)
        local_softmax_feature_2_p3 = self.res_conv5_bn_7(local_softmax_feature_2_p3)

        global_softmax_feats = [global_softmax_feature_p1, global_softmax_feature_p2, global_softmax_feature_p3]
        global_triplet_feats = [global_triplet_feature_p1, global_triplet_feature_p2, global_triplet_feature_p3]
        local_feats = [local_softmax_feature_0_p2, local_softmax_feature_1_p2,
                       local_softmax_feature_0_p3, local_softmax_feature_1_p3, local_softmax_feature_2_p3]
        f = global_softmax_feats + local_feats
        if not self.training:
            return torch.cat(f, dim=1)

        res_conv5_l_p1 = self.res_conv5_fc_0(global_softmax_feature_p1)
        res_conv5_l_p2 = self.res_conv5_fc_1(global_softmax_feature_p2)
        res_conv5_l_p3 = self.res_conv5_fc_2(global_softmax_feature_p3)
        res_conv5_l0_p2 = self.res_conv5_fc_3(local_softmax_feature_0_p2)
        res_conv5_l1_p2 = self.res_conv5_fc_4(local_softmax_feature_1_p2)
        res_conv5_l0_p3 = self.res_conv5_fc_5(local_softmax_feature_0_p3)
        res_conv5_l1_p3 = self.res_conv5_fc_6(local_softmax_feature_1_p3)
        res_conv5_l2_p3 = self.res_conv5_fc_7(local_softmax_feature_2_p3)

        y = [res_conv5_l_p1, res_conv5_l_p2, res_conv5_l_p3,
             res_conv5_l0_p2, res_conv5_l1_p2, res_conv5_l0_p3,
             res_conv5_l1_p3, res_conv5_l2_p3]
        return y, global_triplet_feats


def mgnv2_resnet101_512(num_classes, loss='softmax', **kwargs):
    resnet = resnet101_ibn_a(num_classes, loss=loss, **kwargs)
    model = MGNv2(resnet, num_classes, local_dim=512)
    return model
