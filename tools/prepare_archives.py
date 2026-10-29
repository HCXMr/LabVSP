#!/usr/bin/env python3
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 Chengxuan Huang (黄程宣).
"""在本地创建并逐文件验证数据与仓库压缩包；不上传、不覆盖旧包。"""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import zipfile


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def pack(root):
    root = Path(root).resolve()
    version = json.loads((root / 'metadata/manifest.json').read_text())['version']
    version_tag = 'LabVSP-v' + version
    dist = root / 'dist'
    if dist.exists() or (root / 'metadata/distribution.json').exists():
        raise FileExistsError('压缩包或分发清单已存在。请在新版本目录中打包，保留旧稿。')
    dist.mkdir()
    rows = [json.loads(line) for line in (root / 'metadata/files.jsonl').read_text().splitlines()]
    payload = {r['path']: r for r in rows}
    # 数据附件单独下载时也携带真实许可和引用，数据文件本身保持不变。
    extra_names = ['LICENSE.md', 'LICENSE-DATA.txt', 'LICENSE-CODE.md', 'NOTICE.md', 'CITATION.cff', 'citation.bib']
    for name in extra_names:
        p = root / name
        payload[name] = {'path': name, 'bytes': p.stat().st_size, 'sha256': sha(p)}
    archive = dist / (version_tag + '-data.tar.gz')
    with tarfile.open(archive, 'w:gz', compresslevel=6) as tf:
        for relative in sorted(payload):
            p = root / relative
            if sha(p) != payload[relative]['sha256']:
                raise ValueError('打包前文件校验失败：' + relative)
            info = tf.gettarinfo(str(p), arcname=relative)
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            info.mtime = 0
            info.mode = 0o644
            with p.open('rb') as f:
                tf.addfile(info, f)
    seen = set()
    with tarfile.open(archive, 'r:gz') as tf:
        for member in tf:
            if not member.isfile() or member.name not in payload or member.name in seen:
                raise ValueError('压缩包成员异常：' + member.name)
            content = tf.extractfile(member)
            h = hashlib.sha256()
            for block in iter(lambda: content.read(1024 * 1024), b''):
                h.update(block)
            if h.hexdigest() != payload[member.name]['sha256']:
                raise ValueError('压缩包内容不一致：' + member.name)
            seen.add(member.name)
    if seen != set(payload):
        raise ValueError('压缩包遗漏数据文件。')
    publication = json.loads((root / 'metadata/publication.json').read_text())
    repository_url = publication['repository_url'].rstrip('/')
    release_url = repository_url + '/releases/tag/v' + version
    data_info = {'filename': archive.name, 'bytes': archive.stat().st_size, 'sha256': sha(archive),
                 'url': repository_url + '/releases/download/v' + version + '/' + archive.name,
                 'archive_root': 'data/', 'members': len(seen), 'payload_members': len(rows),
                 'license_and_citation_files': extra_names}
    write_json(root / 'metadata/distribution.json', {'status': 'release', 'version': version,
               'release_url': release_url, 'data_archive': data_info,
               'repository_archive_url': repository_url + '/releases/download/v' + version + '/' + version_tag + '-repository.zip',
               'checksums_url': repository_url + '/releases/download/v' + version + '/SHA256SUMS.txt',
               'download_url_status': '固定版本附件地址；以对应 Release 的公开附件为准'})
    write_json(root / 'reports/archive_validation.json', {'status': 'PASS', 'data_archive': data_info,
               'every_member_matches_payload_sha256': True, 'unsafe_or_unexpected_members': 0})
    repo_archive = dist / (version_tag + '-repository.zip')
    excluded = {'data', 'dist', '_local', '.git', '.venv', '__pycache__'}
    paths = [p for p in root.rglob('*') if p.is_file() and not (set(p.relative_to(root).parts) & excluded)
             and p.suffix not in {'.pyc', '.pyo'}]
    # examples/mini/data 是有意公开的小样例，不应被根目录 data 排除规则误删。
    paths += [p for p in (root / 'examples/mini/data').rglob('*') if p.is_file()]
    paths = sorted(set(paths))
    with zipfile.ZipFile(repo_archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in paths:
            z.write(p, (Path('LabVSP') / p.relative_to(root)).as_posix())
    with zipfile.ZipFile(repo_archive) as z:
        if z.testzip():
            raise ValueError('仓库 ZIP CRC 校验失败。')
        for p in paths:
            if hashlib.sha256(z.read((Path('LabVSP') / p.relative_to(root)).as_posix())).hexdigest() != sha(p):
                raise ValueError('仓库 ZIP 内容不一致：' + str(p))
    repo_info = {'filename': repo_archive.name, 'bytes': repo_archive.stat().st_size, 'sha256': sha(repo_archive), 'members': len(paths)}
    (dist / 'SHA256SUMS.txt').write_text(f'{data_info["sha256"]}  {archive.name}\n{repo_info["sha256"]}  {repo_archive.name}\n')
    write_json(root / '_local/package_validation.json', {'status': 'PASS', 'data': data_info, 'repository': repo_info})
    print(json.dumps({'data': data_info, 'repository': repo_info}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    a = p.parse_args()
    pack(a.root)
