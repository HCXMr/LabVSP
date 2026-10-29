# GitHub 发布与下载

仓库：[HCXMr/LabVSP](https://github.com/HCXMr/LabVSP)。首发标签：[`v1.0.0`](https://github.com/HCXMr/LabVSP/releases/tag/v1.0.0)。版本日期：2026-10-29；下载入口见该固定版本的 Release。

## 仓库和完整数据分开存放

仓库保存 README、文档、标签定义、全量索引、划分、统计、工具、预览和完整小样例。完整 `data/` 通过 Release 附件分发；本地 `data/`、`dist/` 和 `_local/` 由 `.gitignore` 排除。

完整数据展开约 644 MiB。仓库历史与数据压缩包分离可以减少日常克隆体积；GitHub 服务限制以 [大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github) 和 [Release 附件说明](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases) 为准。

## 版本附件

`v1.0.0` 的版本附件：

- `LabVSP-v1.0.0-repository.zip`：仓库内容，不含全量数据或本机来源路径，包含一个完整实例小样例。
- `LabVSP-v1.0.0-data.tar.gz`：全部 9,741 个数据文件，内部路径以 `data/` 开头；根目录另附 6 个许可和引用文件（`LICENSE.md`、`LICENSE-DATA.txt`、`LICENSE-CODE.md`、`NOTICE.md`、`CITATION.cff`、`citation.bib`），共 9,747 个文件。
- `SHA256SUMS.txt`：以上两个压缩包的 SHA-256。

实际文件大小、校验和和地址见 `metadata/distribution.json`。下载后可按下文在本地独立核验；本说明本身不替代远端下载检查记录。

## 下载后使用

将两个压缩包与 `SHA256SUMS.txt` 放在同一目录，然后执行：

```bash
sha256sum -c SHA256SUMS.txt
unzip LabVSP-v1.0.0-repository.zip
tar -xzf LabVSP-v1.0.0-data.tar.gz -C LabVSP
python LabVSP/tools/load_sample.py --root LabVSP/examples/mini
python LabVSP/tools/validate_dataset.py --root LabVSP
```

第一条核对下载文件是否完整。解压后完整数据应在 `LabVSP/data/`，不要形成 `data/data/`。读取工具需要 Python 3.10+、NumPy、Pillow；依赖见 `requirements.txt`。不要向包含自行修改数据的目录直接覆盖解压。

只需检查仓库使用方式时，可以先运行完整小样例；完整数据校验需要数据包已解压。

## 维护者发布检查

1. 在发布副本中更新版本、许可、署名、引用和图片；保持原始数据稿不变。
2. 检查文档链接、数据文件 SHA-256、标签值域、划分和压缩包成员。
3. 同步 `metadata/publication.json`、`metadata/distribution.json`、README 和变更记录。
4. 发布仓库及固定标签的 Release，上传附件。
5. 下载远端附件到独立目录，核对校验和并运行全量校验；据实记录线上可用状态。
6. 若发布后继续修改文档或数据，创建新的版本或后续提交，避免静默替换已引用版本。

## 论文中的引用

论文可引用固定版本入口 `https://github.com/HCXMr/LabVSP/releases/tag/v1.0.0`，并使用 `CITATION.cff` 或 `citation.bib` 中的数据集引用。论文 DOI 尚未确认时不填写占位内容。

如后续需要更持久的学术标识，可将实际发布版本归档至 Zenodo 等仓库；只有归档成功并获得真实 DOI 后，才在引用文件和 Data Availability 中补充该 DOI。GitHub URL 不是 DOI。
