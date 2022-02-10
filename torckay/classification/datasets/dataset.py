import os
import pandas as pd
from PIL import Image
from typing import List, Optional, Tuple

import torch
from torch import Tensor
from torchvision.transforms import transforms as tf

from torckay.classification.augmentations.custom import RandomMixup, RandomCutmix

class CSVDataset(torch.utils.data.Dataset):
    r"""CSVDataset multi-labels classification dataset


    Attributes:
        from_list(**args): Create dataset from list
        from_folder(**args): Create dataset from folder path

    """

    def __init__(
        self,
        image_dir: List[str],
        csv_path: List[str],
        txt_classnames: str,
        transform: Optional[List] = None,
        test: bool = False,
    ):
        super(CSVDataset, self).__init__()
        self.image_dir = image_dir
        self.txt_classnames = txt_classnames
        self.csv_path = csv_path
        self.train = not (test)
        self.transform = transform
        self._load_data()

        if self.train:
            # MixUp and CutMix
            mixup_transforms = []
            mixup_transforms.append(RandomMixup(self.num_classes, p=1.0, alpha=0.2))
            mixup_transforms.append(RandomCutmix(self.num_classes, p=1.0, alpha=1.0))
            self.mixupcutmix = tf.RandomChoice(mixup_transforms)
        else:
            self.mixupcutmix = None

    def _load_data(self):
        self.fns = []
        self.classes_dist = []

        self.classes_idx = {}
        with open(self.txt_classnames, 'r') as f:
            self.classnames = f.read().splitlines()
        
        for idx, classname in enumerate(self.classnames):
            self.classes_idx[classname] = idx
        self.num_classes = len(self.classnames)
        df = pd.read_csv(self.csv_path)
        for _, row in df.iterrows():
            image_name, label = row
            image_path = os.path.join(self.image_dir, image_name)
            self.fns.append([image_path, label])
            self.classes_dist.append(self.classes_idx[label])

    def __getitem__(self, idx: int) -> Tuple[Tensor, Tensor]:

        image_path, label_name = self.fns[idx]
        im = Image.open(image_path).convert('RGB')
        width, height = im.width, im.height
        class_idx = self.classes_idx[label_name]
        transformed = self.transform(im)

        target = {}
        target['labels'] = [class_idx]
        target['label_name'] = label_name

        return {
            "input": transformed, 
            'target': target,
            'img_name': os.path.basename(image_path),
            'ori_size': [width, height]
        }

    def __len__(self) -> int:
        return len(self.fns)

    def collate_fn(self, batch: List):
        imgs = torch.stack([s['input'] for s in batch])
        targets = torch.stack([torch.LongTensor(s['target']['labels']) for s in batch])

        # if self.mixupcutmix is not None:
        #     imgs, targets = self.mixupcutmix(imgs, targets.squeeze(1))
        # targets = targets.float()

        return {
            'inputs': imgs,
            'targets': targets
        }