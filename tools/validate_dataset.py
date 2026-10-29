#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 Chengxuan Huang (黄程宣).
"""只读检查 LabVSP 文件、像素标签、划分、校验和；不是人工语义审核。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def validate(root):
    root = Path(root).resolve()
    m = read(root / 'metadata/manifest.json')
    labels = read(root / 'metadata/label_schema.json')
    split = read(root / 'metadata/splits.json')
    errors, overlaps, duplicate_rgb = [], [], []
    part_pixels, policy_pixels, part_support = Counter(), Counter(), Counter()
    visible_support, functional_support, image_shapes, raw_dtypes = Counter(), Counter(), Counter(), Counter()
    cat_counts, unknown_by_sample = defaultdict(Counter), []
    image_counts, sample_counts = Counter(), Counter()
    rgb_hashes, image_lookup, masks = defaultdict(list), {}, defaultdict(list)
    sync, scales, unverified_scales = [], Counter(), []
    listed_files = {}

    def check(condition, message):
        if not condition:
            errors.append(message)

    def path(relative):
        p = Path(relative)
        if p.is_absolute() or '..' in p.parts or not (root / p).resolve().is_relative_to(root):
            raise ValueError(f'非法相对路径：{relative}')
        return root / p

    def array(relative):
        p = path(relative)
        if p.suffix == '.npy':
            return np.load(p, allow_pickle=False)
        with Image.open(p) as im:
            return np.array(im)

    for line in (root / 'metadata/files.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        p = path(row['path'])
        check(row['path'] not in listed_files, '文件清单重复：' + row['path'])
        listed_files[row['path']] = row
        check(p.is_file(), '缺少文件：' + row['path'])
        if p.is_file():
            check(p.stat().st_size == row['bytes'] and sha(p) == row['sha256'], '文件校验和不一致：' + row['path'])
    actual = {p.relative_to(root).as_posix() for p in (root / 'data').rglob('*') if p.is_file()}
    check(actual == set(listed_files), 'data/ 文件集合与 files.jsonl 不一致')
    check(len({r['sample_id'] for r in m['records']}) == len(m['records']), 'sample_id 重复')
    check(len({r['image_id'] for r in m['images']}) == len(m['images']), 'image_id 重复')
    categories = {c['category_id']: c['name'] for c in read(root / 'metadata/categories.json')}
    for im in m['images']:
        iid = im['image_id']
        image_lookup[iid] = im
        image_counts[im['split']] += 1
        try:
            rgb, depth, valid = [array(im[k]) for k in ('rgb_path', 'depth_path', 'depth_valid_path')]
            shape = (im['height'], im['width'])
            check(rgb.shape == (*shape, 3) and rgb.dtype == np.uint8, iid + ': RGB 格式')
            check(depth.shape == valid.shape == shape, iid + ': 深度尺寸')
            check(np.issubdtype(depth.dtype, np.integer) and depth.min() >= 0 and depth.max() <= 65535, iid + ': 深度数值范围')
            check(set(np.unique(valid)) <= {0, 1, 255}, iid + ': 深度有效掩码编码')
            check(np.array_equal(valid > 0, depth > 0), iid + ': depth_valid != raw_depth > 0')
            camera = read(path(im['camera_path']))
            check((camera['height'], camera['width']) == shape, iid + ': 相机尺寸')
            check(camera.get('rgb_depth_pixel_aligned') is True, iid + ': 缺少像素对齐声明')
            K = np.asarray(camera['K']).reshape(3, 3)
            check(np.isfinite(K).all() and K[0, 0] > 0 and K[1, 1] > 0, iid + ': 相机内参')
            scale = camera['depth_scale_m_per_unit']
            check(isinstance(scale, (float, int)) and scale > 0, iid + ': 深度单位')
            scales[str(scale)] += 1
            if camera.get('depth_scale_sensor_verified') is not True:
                unverified_scales.append(iid)
            sync.append(abs(camera.get('sync_delta_s', 0)))
            image_shapes[str(rgb.shape)] += 1
            raw_dtypes[str(depth.dtype)] += 1
            rgb_hashes[sha(path(im['rgb_path']))].append((iid, im['split']))
        except (OSError, ValueError, KeyError) as e:
            errors.append(iid + ': ' + str(e))
    for r in m['records']:
        sid = r['sample_id']
        try:
            im = image_lookup[r['image_id']]
            shape = (im['height'], im['width'])
            check(r['split'] == im['split'], sid + ': 图像与实例划分冲突')
            check(r['object_id'] in im['object_ids'], sid + ': 对象未在图像登记')
            check(categories[r['category_id']] == r['category'], sid + ': 类别 ID 冲突')
            check(r['object_role'] == split['object_assignment'][r['object_id']], sid + ': 实物分组冲突')
            check(r['object_role'] == ('train' if r['split'] == 'multi_test' else r['split']), sid + ': 实物跨分组泄漏')
            arrays = {k: array(r[k]) for k in ('instance_path', 'part_path', 'policy_path', 'confidence_path', 'provenance_path')}
            check(all(a.shape == shape for a in arrays.values()), sid + ': 标注尺寸')
            ins, part, policy, conf, prov = [arrays[k] for k in ('instance_path', 'part_path', 'policy_path', 'confidence_path', 'provenance_path')]
            inside = ins > 0
            check(bool(inside.any()), sid + ': 空实例')
            check(set(np.unique(ins)) <= {0, 1, 255}, sid + ': 实例不是二值图')
            check(set(np.unique(part)) <= set(range(10)) | {255}, sid + ': 部位值域')
            check(set(np.unique(policy)) <= {0, 1, 2, 3, 255}, sid + ': 策略值域')
            check(not np.any(part[~inside]) and not np.any(policy[~inside]), sid + ': 标签越出实例')
            check(not np.any(part[inside] == 0) and not np.any(policy[inside] == 0), sid + ': 实例内错误背景编码')
            check(conf.dtype == np.float32 and np.isfinite(conf).all() and conf.min() >= 0 and conf.max() <= 1, sid + ': confidence 格式')
            known = inside & np.isin(policy, [1, 2, 3])
            check(np.array_equal(conf, known.astype(np.float32)), sid + ': confidence 与直接标注策略不一致')
            expected_prov = np.zeros(shape, np.uint8)
            expected_prov[inside] = 255
            expected_prov[known] = 1
            check(np.array_equal(prov, expected_prov), sid + ': provenance 不一致')
            folded = np.zeros(shape, np.uint8)
            folded[inside] = 255
            parts = {}
            for layer, support in [('visible_parts', visible_support), ('functional_regions', functional_support)]:
                check(set(r[layer]) == {v['name'] for v in labels[layer]}, sid + ': 层内标签不完整 ' + layer)
                for name, relative in r[layer].items():
                    a = array(relative)
                    check(a.shape == shape and set(np.unique(a)) <= {0, 1, 255}, sid + ': 二值层格式 ' + name)
                    check(not np.any(a[~inside]), sid + ': 层外溢 ' + name)
                    support[name] += int(bool(np.any(a)))
                    if layer == 'visible_parts':
                        parts[name] = a > 0
            ids = {v['name']: v['id'] for v in labels['visible_parts']}
            for name in labels['part_collapse_priority_low_to_high']:
                folded[parts[name] & inside] = ids[name]
            check(np.array_equal(part, folded), sid + ': structural_part_id 与独立部位按优先级折叠不一致')
            for value, count in zip(*np.unique(part[inside], return_counts=True)):
                part_pixels[int(value)] += int(count)
                part_support[int(value)] += 1
            for value, count in zip(*np.unique(policy[inside], return_counts=True)):
                policy_pixels[int(value)] += int(count)
            unknown_by_sample.append({'sample_id': sid, 'instance_pixels': int(inside.sum()),
                                      'part_unknown_pixels': int(np.sum(part[inside] == 255)),
                                      'policy_unknown_pixels': int(np.sum(policy[inside] == 255))})
            masks[r['image_id']].append((r['object_id'], inside))
            sample_counts[r['split']] += 1
            cat_counts[r['category']][r['split']] += 1
        except (OSError, ValueError, KeyError) as e:
            errors.append(sid + ': ' + str(e))
    for iid, members in masks.items():
        check(sorted(x[0] for x in members) == sorted(image_lookup[iid]['object_ids']), iid + ': 图像实例列表不完整')
        for (a, am), (b, bm) in itertools.combinations(members, 2):
            n = int(np.sum(am & bm))
            if n:
                overlaps.append({'image_id': iid, 'objects': [a, b], 'overlap_pixels': n})
    for digest, group in rgb_hashes.items():
        if len(group) > 1:
            duplicate_rgb.append({'sha256': digest, 'images': group})
            check(len({x[1] for x in group}) == 1, 'RGB 字节重复且跨划分：' + str(group))
    check(dict(image_counts) == m['image_counts'], '图像计数与清单不一致')
    check(dict(sample_counts) == m['instance_counts'], '实例计数与清单不一致')
    for s in m['image_counts']:
        actual_ids = sorted(r['image_id'] for r in m['images'] if r['split'] == s)
        listed = (root / 'splits' / (s + '.txt')).read_text().splitlines()
        check(sorted(listed) == actual_ids == sorted(split['image_ids'][s]), s + ': 图像划分清单不一致')
        check(sorted(r['sample_id'] for r in m['records'] if r['split'] == s) == sorted(split['sample_ids'][s]), s + ': 实例划分不一致')
    groups = split['split_objects']
    for a, b in itertools.combinations(groups, 2):
        check(not set(groups[a]) & set(groups[b]), a + '/' + b + ': 实物 ID 重叠')
    for p in (root / 'metadata').glob('*.json*'):
        text = p.read_text(encoding='utf-8')
        check('/home/' not in text and '"/data/' not in text, p.name + ': 本机路径残留')
    return {'status': 'PASS' if not errors else 'FAIL', 'scope': 'all exported images and labels; structural and integrity checks only',
            'errors': errors, 'checked_images': len(m['images']), 'checked_instances': len(m['records']),
            'checked_payload_files': len(listed_files), 'payload_bytes': sum(r['bytes'] for r in listed_files.values()),
            'image_counts': dict(image_counts), 'instance_counts': dict(sample_counts),
            'physical_objects': len(split['object_assignment']), 'category_instance_counts': dict(cat_counts),
            'part_pixel_counts_inside_instances': dict(part_pixels), 'part_instance_support': dict(part_support),
            'policy_pixel_counts_inside_instances': dict(policy_pixels), 'visible_part_instance_support': dict(visible_support),
            'functional_region_instance_support': dict(functional_support), 'rgb_shapes': dict(image_shapes),
            'depth_loaded_dtypes': dict(raw_dtypes), 'declared_depth_scales_m_per_unit': dict(scales),
            'depth_scale_independent_verification_not_recorded_images': len(unverified_scales),
            'rgb_depth_sync_delta_s_range': [min(sync), max(sync)],
            'duplicate_rgb_groups': duplicate_rgb, 'instance_overlap_pairs': overlaps,
            'unknown_by_sample': unknown_by_sample,
            'limitations': ['非逐图人工语义复审', 'raw depth 不是表面真值', 'test 已用于开发验收',
                            'multi_test 是已见实物的新布局', '少量原实例边界重叠保留，不自动重画']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--report', type=Path, help='可选：把检查结果写入指定的新文件。')
    a = p.parse_args()
    result = validate(a.root)
    if a.report:
        if a.report.exists():
            raise FileExistsError('报告已存在，请指定新的报告路径。')
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ['unknown_by_sample', 'instance_overlap_pairs', 'duplicate_rgb_groups']}, ensure_ascii=False, indent=2))
    print('原实例重叠对数：', len(result['instance_overlap_pairs']))
    sys.exit(0 if result['status'] == 'PASS' else 1)
