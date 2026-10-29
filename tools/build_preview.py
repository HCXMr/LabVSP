#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 Chengxuan Huang (黄程宣).
"""用固定样本顺序生成标注预览；仅显示时裁剪，不修改数据。"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


def build(root, output):
    root, output = Path(root), Path(output)
    if output.exists():
        raise FileExistsError('预览文件已存在，请指定新的输出文件。')
    m = json.loads((root / 'metadata/manifest.json').read_text())
    schema = json.loads((root / 'metadata/label_schema.json').read_text())
    categories = json.loads((root / 'metadata/categories.json').read_text())
    images = {r['image_id']: r for r in m['images']}
    font = ImageFont.truetype('DejaVuSans.ttf', 17)
    small = ImageFont.truetype('DejaVuSans.ttf', 14)
    title = ImageFont.truetype('DejaVuSans.ttf', 30)
    W, cell_w, cell_h, row_h = 1240, 232, 190, 232
    canvas = Image.new('RGB', (W, 1780), '#f3f5f8')
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 16), 'LabVSP | RGB-D and four annotation layers', fill='#13293d', font=title)
    draw.text((24, 57), 'LabVSP v1.0.0 | Fixed median sample per category; display crops only.', fill='#475569', font=font)
    for j, label in enumerate(['RGB', 'Instance', 'Visible parts', 'Functional regions', 'Contact policy']):
        draw.text((24 + j * 244, 90), label, fill='#13293d', font=font)
    selected = []

    def arr(rel):
        with Image.open(root / rel) as im:
            return np.array(im)

    def overlay(rgb, indexed, colors):
        out = rgb.astype(np.float32).copy()
        for k, color in colors.items():
            use = indexed == k
            out[use] = .38 * out[use] + .62 * np.array(color)
        return np.uint8(np.clip(out, 0, 255))

    part_colors = {p['id']: p['color_bgr'][::-1] for p in schema['visible_parts']}
    policy_colors = {p['id']: p['color_bgr'][::-1] for p in schema['contact_policy']}
    part_colors[255] = policy_colors[255] = [155, 155, 155]
    for i, category in enumerate(categories):
        candidates = sorted([r for r in m['records'] if r['category_id'] == category['category_id'] and r['dataset'] == 'single'], key=lambda r: r['sample_id'])
        r = candidates[len(candidates) // 2]
        selected.append({'category': category['name'], 'sample_id': r['sample_id'], 'selection': 'middle_index_of_sorted_single_samples'})
        rgb, instance = arr(images[r['image_id']]['rgb_path']), arr(r['instance_path']) > 0
        yy, xx = np.where(instance)
        box = (max(0, int(xx.min()) - 20), max(0, int(yy.min()) - 20), min(640, int(xx.max()) + 21), min(480, int(yy.max()) + 21))
        funcs = np.zeros(instance.shape, np.uint8)
        for p in schema['functional_regions']:
            funcs[arr(r['functional_regions'][p['name']]) > 0] = p['id']
        views = [rgb, overlay(rgb, instance.astype(np.uint8), {1: [30, 180, 220]}),
                 overlay(rgb, arr(r['part_path']), part_colors),
                 overlay(rgb, funcs, {p['id']: p['color_bgr'][::-1] for p in schema['functional_regions']}),
                 overlay(rgb, arr(r['policy_path']), policy_colors)]
        y = 122 + i * row_h
        draw.text((24, y), f'{category["name"]}  |  {r["object_id"]}  |  {r["split"]}', fill='#13293d', font=small)
        for j, v in enumerate(views):
            panel = ImageOps.pad(Image.fromarray(v).crop(box), (cell_w, cell_h), color='white')
            canvas.paste(panel, (24 + 244 * j, y + 24))
    draw.text((24, 1752), 'Colors: metadata/label_schema.json. Overlapping functional masks remain independent in data/.', fill='#475569', font=small)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    output.with_suffix('.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2) + '\n')
    print(output)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    build(a.root, a.output)
