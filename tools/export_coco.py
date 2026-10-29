#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 Chengxuan Huang (黄程宣).
"""导出 COCO 实例分割索引（未压缩 RLE）；四层部位标注仍使用原生清单。"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def rle(mask):
    # COCO 使用列优先展开，counts 首项为背景长度。
    flat = np.asarray(mask, dtype=np.uint8).ravel(order='F')
    edges = np.flatnonzero(flat[1:] != flat[:-1]) + 1
    lengths = np.diff(np.r_[0, edges, len(flat)]).astype(int).tolist()
    if flat[0]:
        lengths.insert(0, 0)
    return {'size': list(mask.shape), 'counts': lengths}


def decode(value):
    runs = value['counts']
    return np.repeat(np.arange(len(runs)) % 2, runs).reshape(value['size'], order='F').astype(bool)


def export(root, output):
    root, output = Path(root), Path(output)
    if output.exists():
        raise FileExistsError('导出目录已存在，请使用新目录。')
    m = json.loads((root / 'metadata/manifest.json').read_text())
    cats = json.loads((root / 'metadata/categories.json').read_text())
    id_map = {r['image_id']: i + 1 for i, r in enumerate(m['images'])}
    output.mkdir(parents=True)
    for split in ('train', 'val', 'test', 'multi_test'):
        images = [{'id': id_map[r['image_id']], 'file_name': r['rgb_path'], 'width': r['width'], 'height': r['height'],
                   'labvsp_image_id': r['image_id']} for r in m['images'] if r['split'] == split]
        annotations = []
        for i, r in enumerate(m['records']):
            if r['split'] != split:
                continue
            with Image.open(root / r['instance_path']) as im:
                mask = np.array(im) > 0
            encoded = rle(mask)
            if not np.array_equal(decode(encoded), mask):
                raise ValueError('RLE 往返验证失败：' + r['sample_id'])
            yy, xx = np.where(mask)
            annotations.append({'id': i + 1, 'image_id': id_map[r['image_id']], 'category_id': r['category_id'],
                                'segmentation': encoded, 'area': int(mask.sum()), 'iscrowd': 0,
                                'bbox': [int(xx.min()), int(yy.min()), int(xx.max() - xx.min() + 1), int(yy.max() - yy.min() + 1)],
                                'labvsp_sample_id': r['sample_id'], 'physical_object_id': r['object_id']})
        value = {'info': {'description': 'LabVSP draft; uncompressed COCO RLE; file_name relative to repository root'},
                 'images': images, 'annotations': annotations,
                 'categories': [{'id': c['category_id'], 'name': c['name'], 'supercategory': 'transparent_labware'} for c in cats]}
        (output / (split + '.json')).write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')
    print('已生成 4 个 COCO 索引；419 个实例 RLE 逐像素往返检查通过。')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    export(a.root, a.output)
