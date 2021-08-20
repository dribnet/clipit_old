from DrawingInterface import DrawingInterface

import pydiffvg
import torch
from torch.nn import functional as F
import skimage
import skimage.io
import random
import ttools.modules
import argparse
import math
import torchvision
import torchvision.transforms as transforms
import numpy as np
import PIL.Image

pydiffvg.set_print_timing(False)

# https://discuss.pytorch.or
class PixelDrawer(DrawingInterface):
    num_rows = 45
    num_cols = 80
    do_mono = False
    pixels = []

    def __init__(self, width, height, do_mono, shape=None):
        super(DrawingInterface, self).__init__()

        self.canvas_width = width
        self.canvas_height = height
        self.do_mono = do_mono
        if shape is not None:
            self.num_cols, self.num_rows = shape


    def load_model(self, config_path, checkpoint_path, device):
        # gamma = 1.0

        # Use GPU if available
        pydiffvg.set_use_gpu(torch.cuda.is_available())
        pydiffvg.set_device(device)
        self.device = device

        canvas_width, canvas_height = self.canvas_width, self.canvas_height
        num_rows, num_cols = self.num_rows, self.num_cols
        cell_width = canvas_width / num_cols
        cell_height = canvas_height / num_rows

        # Initialize Random Pixels
        shapes = []
        shape_groups = []
        colors = []
        for r in range(num_rows):
            cur_y = r * cell_height
            for c in range(num_cols):
                cur_x = c * cell_width
                cell_color = torch.tensor([random.random(), random.random(), random.random(), 1.0])
                colors.append(cell_color)
                p0 = [cur_x, cur_y]
                p1 = [cur_x+cell_width, cur_y+cell_height]
                path = pydiffvg.Rect(p_min=torch.tensor(p0), p_max=torch.tensor(p1))
                shapes.append(path)
                path_group = pydiffvg.ShapeGroup(shape_ids = torch.tensor([len(shapes) - 1]), stroke_color = None, fill_color = cell_color)
                shape_groups.append(path_group)

        # Just some diffvg setup
        scene_args = pydiffvg.RenderFunction.serialize_scene(\
            canvas_width, canvas_height, shapes, shape_groups)
        render = pydiffvg.RenderFunction.apply
        img = render(canvas_width, canvas_height, 2, 2, 0, None, *scene_args)

        color_vars = []
        for group in shape_groups:
            group.fill_color.requires_grad = True
            color_vars.append(group.fill_color)

        # Optimizers
        # points_optim = torch.optim.Adam(points_vars, lr=1.0)
        # width_optim = torch.optim.Adam(stroke_width_vars, lr=0.1)
        color_optim = torch.optim.Adam(color_vars, lr=0.02)

        self.img = img
        self.shapes = shapes 
        self.shape_groups  = shape_groups
        self.opts = [color_optim]

    def get_opts(self):
        return self.opts

    def rand_init(self, toksX, toksY):
        # TODO
        pass

    def init_from_tensor(self, init_tensor):
        # TODO
        pass

    def reapply_from_tensor(self, new_tensor):
        # TODO
        pass

    def get_z_from_tensor(self, ref_tensor):
        return None

    def get_num_resolutions(self):
        # TODO
        return 5

    def synth(self, cur_iteration):
        render = pydiffvg.RenderFunction.apply
        scene_args = pydiffvg.RenderFunction.serialize_scene(\
            self.canvas_width, self.canvas_height, self.shapes, self.shape_groups)
        img = render(self.canvas_width, self.canvas_height, 2, 2, cur_iteration, None, *scene_args)
        img_h, img_w = img.shape[0], img.shape[1]
        img = img[:, :, 3:4] * img[:, :, :3] + torch.ones(img.shape[0], img.shape[1], 3, device = self.device) * (1 - img[:, :, 3:4])
        img = img[:, :, :3]

        if self.do_mono:
            # transform this to mono-ish image (I made this up!)
            darkness = img[:,:,1] - img[:,:,0]
            darkness = darkness + torch.normal(0.0, 0.5, size=(img_h, img_w), device = self.device)
            # sig_scale = torch.randn(size=(1,))[0]
            # sig_scale = torch.rand(size=(img_h, img_w), device = self.device)
            # img = torch.sigmoid(40 * sig_scale * darkness)
            img = torch.sigmoid(40 * darkness)

            # img = img[:,:,1] # use the green channel for now
            # if cur_iteration > 0:
            #     # gumbel time - add some gaussian noise to img
            #     black = black + torch.normal(0.5, 0.1, size=(img_h, img_w), device = self.device)
            # if cur_iteration == 0:
            #     # threshold is 0.5 in "canonical" case
            #     random_threshold = 0.5 * torch.ones(size=(img_h, img_w), device = self.device, requires_grad=True)
            # else:
            #     # threshold when training is a pixelwise approximate gaussian from [0,1]
            #     random_threshold = torch.mean(torch.rand(size=(5, img_h, img_w), device = self.device, requires_grad=True), axis=0)
            # pimg = PIL.Image.fromarray(np.uint8(random_bates*255), mode="L")
            # pimg.save("bates_debug.png")
            # img = torch.where(img > random_threshold, 1.0, 0.0, requires_grad=True)
            img = torch.stack([img, img, img])
            img = img.permute(1, 2, 0)
            img.requres_grad = True

        img = img.unsqueeze(0)
        img = img.permute(0, 3, 1, 2) # NHWC -> NCHW
        # if cur_iteration == 0:
        #     print("SHAPE", img.shape)

        self.img = img
        return img

    @torch.no_grad()
    def to_image(self):
        img = self.img.detach().cpu().numpy()[0]
        img = np.transpose(img, (1, 2, 0))
        img = np.clip(img, 0, 1)
        img = np.uint8(img * 255)
        pimg = PIL.Image.fromarray(img, mode="RGB")
        return pimg

    def clip_z(self):
        with torch.no_grad():
            for group in self.shape_groups:
                group.fill_color.data[:3].clamp_(0.0, 1.0)
                group.fill_color.data[3].clamp_(1.0, 1.0)

    def get_z(self):
        return None

    def get_z_copy(self):
        return None
