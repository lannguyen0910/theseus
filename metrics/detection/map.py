import os
import torch
import json
import numpy as np
from tqdm import tqdm
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
from metrics import TemplateMetric
from utils.utils import postprocessing, box_nms_numpy

"""
    Example use:
        metric = mAPScores(
                    dataset = testset,
                    min_conf = 0.3,
                    min_iou = 0.3,
                    retransforms = Compose([
                        Denormalize(box_transform=False),
                        ToPILImage(),
                        Resize(size = (626, 626))]))
"""


def _eval(coco_gt, image_ids, pred_json_path, **kwargs):
    # load results in COCO evaluation tool
    coco_pred = coco_gt.loadRes(pred_json_path)

    # run COCO evaluation
    coco_eval = COCOeval(coco_gt, coco_pred, 'bbox')
    coco_eval.params.imgIds = image_ids

    coco_eval.params.maxDets[2] = kwargs['max_detection']
    # Some params for COCO eval
    #imgIds = []
    #catIds = []
    #iouThrs = np.linspace(.5, 0.95, int(np.round((0.95 - .5) / .05)) + 1, endpoint=True)
    #recThrs = np.linspace(.0, 1.00, int(np.round((1.00 - .0) / .01)) + 1, endpoint=True)
    #maxDets = [1, 10, 100]
    #areaRng = [[0 ** 2, 1e5 ** 2], [0 ** 2, 32 ** 2], [32 ** 2, 96 ** 2], [96 ** 2, 1e5 ** 2]]
    #areaRngLbl = ['all', 'small', 'medium', 'large']
    #useCats = 1

    coco_eval.evaluate()
    coco_eval.accumulate()
    coco_eval.summarize()
    stats = coco_eval.stats
    return stats

class mAPScores(TemplateMetric):
    def __init__(
            self,
            dataset, 
            max_images = 10000,
            retransforms=None,
            min_conf = 0.3, 
            min_iou = 0.3, 
            decimals = 4):

        self.coco_gt = COCO(dataset.ann_path)
        self.dataloader = torch.utils.data.DataLoader(
                dataset, 
                batch_size=1, 
                num_workers=4, 
                pin_memory = True,
                drop_last= True, 
                collate_fn=dataset.collate_fn) # requires batch size = 1

        self.retransforms = retransforms
        self.min_conf = min_conf
        self.min_iou = min_iou
        self.max_images = max_images
        self.max_detection = max_detection
        self.filepath = f'results/bbox_results.json'
        self.image_ids = []
        self.reset()

        if not os.path.exists('results'):
            os.mkdir('results')

    def reset(self):
        self.model = None
        self.image_ids = []

    def update(self, model):
        self.model = model
        self.model.eval()

    def compute(self):
        results = []
        empty_imgs = 0
        with torch.no_grad():
            pbar = tqdm(self.dataloader)
            with tqdm(total=min(len(self.dataloader), self.max_images)) as pbar:
                for idx, batch in enumerate(self.dataloader):
                    if idx > self.max_images:
                        break
                    image_id = batch['img_ids'][0]
                    self.image_ids.append(image_id)
                    batch['imgs'] = batch['imgs'].to(self.model.device)
                    preds = self.model.inference_step(batch, self.min_conf, self.min_iou)
                    preds = postprocessing(preds, batch['imgs'].cpu()[0], self.retransforms, out_format='xywh')

                    try:
                        bbox_xywh = np.concatenate([i['bboxes'] for i in preds if len(i['bboxes'])>0]) 
                        cls_ids = np.concatenate([i['classes'] for i in preds if len(i['bboxes'])>0])    
                        cls_conf = np.concatenate([i['scores'] for i in preds if len(i['bboxes'])>0])
                        bbox_xywh, cls_conf, cls_ids = box_nms_numpy(bbox_xywh, cls_conf, cls_ids, threshold=self.min_iou, box_format='xywh')
                    except:
                        bbox_xywh = None
                        cls_ids = None
                        cls_conf = None

                    if bbox_xywh is None:
                        empty_imgs += 1
                        continue

                    for i in range(bbox_xywh.shape[0]):
                        score = float(cls_conf[i])
                        label = int(cls_ids[i])
                        box = bbox_xywh[i, :]
                        image_result = {
                            'image_id': image_id,
                            'category_id': label + 1,
                            'score': float(score),
                            'bbox': box.tolist(),
                        }

                        results.append(image_result)
                    pbar.update(1)
                    pbar.set_description(f'Empty images: {empty_imgs}')

        if not len(results):
            raise Exception('the model does not provide any valid output, check model architecture and the data input')

        # write output
        if os.path.exists(self.filepath):
            os.remove(self.filepath)
        json.dump(results, open(self.filepath, 'w'), indent=4)

    def value(self):
        self.compute()
        stats = _eval(self.coco_gt, self.image_ids, self.filepath, max_detection=self.max_detection)
        return {
            "MAP" : stats[0],
            "MAPsmall" : stats[1],
            "mAPmedium" : stats[2],
            "mAPlarge" : stats[3],}

    def __str__(self):
        return f'Mean Average Precision: {self.value()}'

    def __len__(self):
        return len(self.dataloader)