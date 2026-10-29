#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 Chengxuan Huang (黄程宣).
"""读取一个实例及其完整 RGB-D 图像；不裁剪、不缩放、不重映射标签。"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def load_sample(root, sample_id=None, split='train'):
    root = Path(root)
    manifest = json.loads((root / 'metadata/manifest.json').read_text(encoding='utf-8'))
    rows = [r for r in manifest['records'] if r['sample_id'] == sample_id] if sample_id else [r for r in manifest['records'] if r['split'] == split]
    if not rows:
        raise ValueError('未找到指定样本或分割。')
    row = rows[0]
    image = next(x for x in manifest['images'] if x['image_id'] == row['image_id'])

    def png(relative):
        with Image.open(root / relative) as im:
            return np.array(im)

    camera = json.loads((root / image['camera_path']).read_text())
    depth_raw = png(image['depth_path']).astype(np.uint16)
    output = {'metadata': row, 'camera': camera, 'rgb': png(image['rgb_path']), 'depth_raw': depth_raw,
              'depth_m': depth_raw.astype(np.float32) * camera['depth_scale_m_per_unit'],
              'depth_valid': png(image['depth_valid_path']) > 0,
              'instance': png(row['instance_path']) > 0, 'part_id': png(row['part_path']),
              'policy_id': png(row['policy_path']), 'confidence': np.load(root / row['confidence_path'], allow_pickle=False),
              'provenance_id': png(row['provenance_path']),
              'visible_parts': {k: png(v) > 0 for k, v in row['visible_parts'].items()},
              'functional_regions': {k: png(v) > 0 for k, v in row['functional_regions'].items()}}
    return output


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--sample-id')
    p.add_argument('--split', default='train', choices=['train', 'val', 'test', 'multi_test'])
    a = p.parse_args()
    s = load_sample(a.root, a.sample_id, a.split)
    print(s['metadata']['sample_id'])
    for k, v in s.items():
        if isinstance(v, np.ndarray):
            print(f'{k}: shape={v.shape}, dtype={v.dtype}')
    print('说明：depth_m 按记录单位换算，零深度无效；confidence 是标注来源指示，不是深度置信度。')
