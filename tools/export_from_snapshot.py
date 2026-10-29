#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 Chengxuan Huang (黄程宣).
"""从现有 LabGlass 冻结清单导出可移植副本；拒绝覆盖已生成的数据。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil

VERSION = '0.1.0-draft'
SPLITS = ('train', 'val', 'test', 'multi_test')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n' for r in rows), encoding='utf-8')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def image_id(key):
    return key.replace('/', '__')


def export(manifest_path, root):
    manifest_path, root = Path(manifest_path).resolve(), Path(root).resolve()
    if (root / 'metadata/manifest.json').exists() or (root / 'data').exists():
        raise FileExistsError('输出已经包含数据，请使用一个新的目录。')
    m = read(manifest_path)
    if len(m['records']) != sum(m['instance_counts'].values()):
        raise ValueError('清单 records 不完整；请使用包含 multi_test 的完整 manifest.json。')
    base = manifest_path.parent
    snapshot = base / 'snapshot'
    labels = read(snapshot / 'single/configs/annotations/label_schema_v2.json')
    categories = read(base / 'taxonomy.json')['categories']
    root.mkdir(parents=True, exist_ok=True)
    source_index = {str(Path(r['snapshot']).resolve()): r for r in m['files']}
    source_stats, sources, payload, raw_differences = {}, [], [], []

    def track_source(src):
        src = Path(src).resolve()
        key = str(src)
        if key in source_stats:
            return source_stats[key]['sha256']
        stat = src.stat()
        digest = sha(src)
        expected = source_index.get(key, {}).get('sha256')
        if expected and digest != expected:
            raise ValueError(f'冻结文件的 SHA-256 与原清单不一致：{src}')
        source_stats[key] = {'sha256': digest, 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
        original = source_index.get(key, {}).get('source')
        if original:
            current = sha(original) if Path(original).is_file() else None
            if current != digest:
                raw_differences.append({'snapshot': key, 'original': original, 'snapshot_sha256': digest, 'current_sha256': current})
        return digest

    def record_payload(dst, kind):
        payload.append({'path': dst.relative_to(root).as_posix(), 'bytes': dst.stat().st_size, 'sha256': sha(dst), 'kind': kind})

    def copy(src, relative, kind):
        src, dst = Path(src), root / relative
        digest = track_source(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if sha(dst) != digest or (src.stat().st_dev, src.stat().st_ino) == (dst.stat().st_dev, dst.stat().st_ino):
            raise ValueError(f'副本校验失败：{dst}')
        sources.append({'source': str(src), 'destination': relative, 'source_sha256': digest, 'operation': 'byte_copy'})
        record_payload(dst, kind)
        return relative

    def transformed(src, relative, value, kind, description):
        digest = track_source(src)
        dst = root / relative
        save(dst, value)
        sources.append({'source': str(src), 'destination': relative, 'source_sha256': digest, 'operation': description})
        record_payload(dst, kind)
        return relative

    # 公开元数据不包含本机绝对路径、标注者账号或采集阶段遗留的未完成状态。
    scene_fields = ('schema_version', 'session_id', 'scene_id', 'object_id', 'object_ids', 'category', 'category_id',
                    'yaw_deg', 'view_group', 'condition_id', 'capture_method', 'created_at_utc',
                    'formal_image_contains_calibration_board', 'source_rgb_encoding', 'source_depth_encoding',
                    'depth_valid_definition', 'selected_record_offset_s', 'layout_group_id')
    annotation_fields = ('schema_version', 'session_id', 'scene_id', 'object_id', 'category', 'category_id',
                         'instance_id', 'updated_at_utc', 'image_size', 'visible_only', 'hidden_semantics_completed',
                         'policy_unknown_value', 'human_direct_evidence', 'source_type')
    images, rows = [], []
    by_image = defaultdict(list)
    for r in m['records']:
        by_image[r['image_key']].append(r)
    for i, source_image in enumerate(sorted(m['images'], key=lambda x: x['image_key'])):
        key = source_image['image_key']
        iid, rec = image_id(key), by_image[key][0]
        scene = Path(rec['scene_dir'])
        out = {'image_id': iid, 'source_image_key': key, 'dataset': rec['dataset'], 'split': rec['split'],
               'session_id': rec['session_id'], 'scene_id': rec['scene_id'],
               'width': source_image['width'], 'height': source_image['height'],
               'object_ids': sorted(r['object_id'] for r in by_image[key])}
        for field, source_name, folder in [('rgb_path', 'color.png', 'rgb'), ('depth_path', 'depth_raw.png', 'depth'),
                                           ('depth_valid_path', 'depth_valid.png', 'depth_valid')]:
            out[field] = copy(scene / source_name, f'data/{folder}/{iid}.png', folder)
        out['camera_path'] = copy(scene / 'camera_info.json', f'data/camera/{iid}.json', 'camera')
        sc = read(scene / 'scene.json')
        sm = {k: sc[k] for k in scene_fields if k in sc}
        sm['metadata_scope'] = 'capture_time_only; use metadata/manifest.json for current split and annotations'
        out['scene_path'] = transformed(scene / 'scene.json', f'data/scenes/{iid}.json', sm, 'scene', 'select_scientific_capture_fields')
        images.append(out)
        if (i + 1) % 100 == 0:
            print(f'已复制 RGB-D：{i + 1}/{len(m["images"])}', flush=True)
    image_lookup = {r['source_image_key']: r for r in images}
    for i, r in enumerate(sorted(m['records'], key=lambda x: x['sample_id'])):
        im = image_lookup[r['image_key']]
        iid, oid = im['image_id'], r['object_id']
        sample_id = f'{iid}__{oid}'
        ad = Path(r['annotation_dir'])
        target = f'data/annotations/{iid}/{oid}'
        row = {'sample_id': sample_id, 'source_sample_id': r['sample_id'], 'image_id': iid,
               'dataset': r['dataset'], 'split': r['split'], 'object_id': oid,
               'object_role': m['object_assignment'][oid], 'category_id': r['category_id'], 'category': r['category'],
               'annotation_dir': target}
        for field, filename in [('instance_path', 'instance_mask.png'), ('part_path', 'structural_part_id.png'),
                                ('policy_path', 'contact_policy_id.png'), ('confidence_path', 'confidence_f32.npy'),
                                ('provenance_path', 'provenance_id.png')]:
            row[field] = copy(ad / filename, f'{target}/{filename}', 'annotation')
        for layer in ('visible_parts', 'functional_regions'):
            row[layer] = {label['name']: copy(ad / layer / (label['name'] + '.png'),
                                            f'{target}/{layer}/{label["name"]}.png', layer) for label in labels[layer]}
        old = read(ad / 'annotations_v2.json')
        ann = {k: old[k] for k in annotation_fields if k in old}
        ann['label_schema'] = 'metadata/label_schema.json'
        ann['path_resolution'] = 'repository_root'
        ann['sample_id'] = sample_id
        state = ad / 'state.json'
        if state.exists():
            track_source(state)
            s = read(state)
            ann['historical_review'] = {k: s[k] for k in ('status', 'identity_confirmed', 'four_layers_reviewed', 'confirmed_at') if k in s}
        row['annotation_metadata_path'] = transformed(ad / 'annotations_v2.json', f'{target}/annotation.json', ann,
                                                    'annotation_metadata', 'select_fields_remove_annotator_relocate_schema')
        rows.append(row)
        if (i + 1) % 100 == 0:
            print(f'已复制四层标注：{i + 1}/{len(m["records"])}', flush=True)
    objects = []
    for oid in sorted(m['object_assignment']):
        src = snapshot / 'single/objects' / oid / 'object.json'
        track_source(src)
        obj = read(src)
        obj.pop('created_by', None)
        obj['split'] = m['object_assignment'][oid]
        objects.append(obj)
    track_source(manifest_path)
    track_source(base / 'taxonomy.json')
    track_source(snapshot / 'single/configs/annotations/label_schema_v2.json')
    save(root / 'metadata/objects.json', objects)
    save(root / 'metadata/categories.json', categories)
    save(root / 'metadata/label_schema.json', labels)
    save(root / 'metadata/splits.json', {'protocol_version': m['protocol_version'], 'seed': m['seed'],
         'object_assignment': m['object_assignment'], 'split_objects': m['split_objects'],
         'test_is_development_holdout': True, 'multi_test_is_seen_objects_new_layouts': True,
         'multi_test_object_ids': m['multi_test_object_ids'],
         'image_ids': {s: [i['image_id'] for i in images if i['split'] == s] for s in SPLITS},
         'sample_ids': {s: [i['sample_id'] for i in rows if i['split'] == s] for s in SPLITS}})
    for s in SPLITS:
        p = root / 'splits' / (s + '.txt')
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(''.join(i['image_id'] + '\n' for i in images if i['split'] == s), encoding='utf-8')
    public = {'schema_version': 'labvsp.manifest.v1', 'name': 'LabVSP', 'version': VERSION, 'status': 'draft',
              'created_date': '2026-10-18', 'path_base': 'repository_root', 'image_counts': dict(Counter(x['split'] for x in images)),
              'instance_counts': dict(Counter(x['split'] for x in rows)), 'images': images, 'records': rows}
    save(root / 'metadata/manifest.json', public)
    jsonl(root / 'metadata/images.jsonl', images)
    jsonl(root / 'metadata/instances.jsonl', rows)
    save(root / 'metadata/source_provenance.json', {'source_dataset_name': 'LabGlass Visible-Only RC2.2',
         'source_snapshot_name': manifest_path.parent.parent.name, 'source_manifest_sha256': sha(manifest_path),
         'export_version': VERSION, 'image_and_array_transform': 'none; independent byte-identical copies',
         'metadata_transform': 'relative paths; remove account identifiers; capture fields only; historical review kept separately',
         'raw_sources_compared': True, 'raw_snapshot_difference_count': len(raw_differences)})
    save(root / 'metadata/publication.json', {'status': 'draft', 'title': 'LabVSP', 'full_name': None,
         'authors': [], 'team': None, 'contact': None, 'data_license': None, 'code_license': None,
         'paper_title': None, 'paper_url': None, 'paper_doi': None, 'repository_url': None, 'dataset_doi': None,
         'release_url': None, 'publication_year': None,
         'note_zh': '用户将于论文完成后补充上述信息，然后再发布；未确定字段保持空值。'})
    jsonl(root / 'metadata/files.jsonl', sorted(payload, key=lambda x: x['path']))
    jsonl(root / '_local/source_mapping.jsonl', sources)
    changed = []
    for p, info in source_stats.items():
        stat = Path(p).stat()
        if stat.st_size != info['size'] or stat.st_mtime_ns != info['mtime_ns']:
            changed.append(p)
    audit = {'source_manifest': str(manifest_path), 'source_manifest_sha256': sha(manifest_path),
             'tracked_source_files': len(source_stats), 'source_change_during_export': changed,
             'raw_snapshot_differences': raw_differences, 'payload_files': len(payload),
             'payload_bytes': sum(p['bytes'] for p in payload), 'byte_copies': sum(x['operation'] == 'byte_copy' for x in sources),
             'historical_snapshot_hashes_verified': sum(p in source_index for p in source_stats)}
    save(root / '_local/source_audit.json', audit)
    save(root / '_local/source_baseline.json', source_stats)
    if changed:
        raise RuntimeError('导出期间源文件发生变化，见本地审计报告。')
    print(json.dumps({k: v for k, v in audit.items() if k != 'raw_snapshot_differences'}, ensure_ascii=False), flush=True)
    print('当前原始库与冻结副本不同文件数：', len(raw_differences), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-manifest', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    export(a.source_manifest, a.output)
