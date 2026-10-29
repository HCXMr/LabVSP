# LabVSP 数据集

**版本：`1.0.0`（2026-10-29）。** 数据及标注按 **CC BY-NC 4.0（署名—非商业性使用）** 提供。

**作者：黄程宣（Chengxuan Huang）**，周利锋课题组博士研究生。
**团队：南方科技大学工学院机械与能源工程系周利锋课题组。**
**仓库：[HCXMr/LabVSP](https://github.com/HCXMr/LabVSP)** · [联系与问题反馈](https://github.com/HCXMr/LabVSP/issues)。

论文正在撰写，论文标题和论文 DOI 将在确认后补充。数据集本身可先独立引用。

[English](README.en.md) · [数据说明](docs/DATASET_CARD.md) · [文件与标签格式](docs/FORMAT.md) · [发布数据复核](reports/release_validation.json) · [后续补充信息](docs/待补充信息.md)

LabVSP 面向透明实验器皿的部位级视觉理解和接触策略标注，包含对齐的 RGB-D 图像，以及**实例、可见部位、功能区域、接触策略**四层标注。本数据集由既有 LabGlass Visible-Only 数据及研究使用的冻结清单整理而来。`1.0.0` 的数据内容与 `0.1.0-draft` 相同；本次更新发布说明、署名、许可、引用和展示素材，保留原图、标签数值、实物编号与数据划分。

![LabVSP 数据集概览：器皿类别、场景及多层标注](assets/dataset_overview.png)

概览图介绍器皿类别、场景多样性和标注层次。下文另提供七类器皿的详细标注预览。

## 数据概况

| 项目 | 数量 / 说明 |
|---|---|
| 器皿类别 | 7 类 |
| 不同实体器皿 | 30 个 |
| RGB-D 图像对 | 356 对，均为 640 × 480 |
| 单物体 / 多物体图像 | 331 / 25 |
| 标注实例 | 419 个：单物体 331，多物体 88 |
| 部位类别 | 定义 9 种，当前实际出现 8 种；`handle=6` 无标注像素 |
| 功能区域 / 接触策略 | 4 / 3 种 |
| 完整本地数据 | 9,741 个文件，675,032,703 字节，约 644 MiB |

| 划分 | 图像 | 实例 | 含义 |
|---|---:|---:|---|
| `train` | 195 | 244 | 175 张单物体图像 + 20 张多物体图像 |
| `val` | 81 | 81 | 7 个验证实物 |
| `test` | 75 | 75 | 7 个开发留出实物，已用于开发验收 |
| `multi_test` | 5 | 19 | 训练已见实物的 5 个新布局 |

单物体按实物 ID 分组，`train/val/test` 分别为 16/7/7 个实物且互不重叠。**`test` 不是未接触过的盲测集；`multi_test` 也不是未知实物测试集。** 不要把相同实物的不同视角随机分配到训练和测试。

![七类器皿及四层标注](assets/annotation_overview.png)

详细预览每类固定选取按样本 ID 排序后的中间样本，仅为显示裁剪；完整数据保持 640 × 480。两张图采用各自的展示配色，概览图的颜色图例只解释该图；机器读取时以 [标签字典](metadata/label_schema.json) 中的名称和数值 ID 为准，不应跨图按颜色解码。预览不是全面人工语义审核。

## 目录

```text
LabVSP/
├── README.md / README.en.md
├── CITATION.cff / citation.bib # 数据集引用
├── LICENSE.md                # 数据与代码的许可范围
├── LICENSE-DATA.txt / LICENSE-CODE.md
├── metadata/                 # 图像/实例索引、标签字典、实物信息、划分、文件哈希
│   ├── manifest.json         # 完整入口：356 个 images + 419 个 records
│   ├── images.jsonl / instances.jsonl
│   ├── categories.json / label_schema.json / objects.json
│   ├── splits.json / publication.json / files.jsonl
│   └── coco/                 # 4 个 COCO 实例分割索引
├── splits/                   # 每行一个 image_id
├── data/                     # 全量数据；本地保留，默认不提交普通 Git
│   ├── rgb/ / depth/ / depth_valid/
│   ├── camera/ / scenes/
│   └── annotations/<image_id>/<object_id>/
├── examples/mini/            # 一个完整实例的便携读取示例
├── assets/                   # 数据集概览、七类标注预览及选样记录
├── tools/                    # 导出、校验、读取、COCO、预览、打包
├── docs/                     # 格式、数据卡、补充表、发布说明
├── reports/                  # 可复核的检查结果
├── dist/                     # 本地发布压缩包，默认不提交 Git
└── _local/                   # 本机来源路径和核验记录，默认不提交 Git
```

## 读取与检查

Python 3.10 及以上，需要 NumPy、Pillow。可在自己的虚拟环境安装 `requirements.txt` 中的依赖。全量读取和校验需要先按下文说明下载数据包。

在这个目录运行以下两条命令即可分别读取样本、检查全量数据；它们不会修改数据：

```bash
python tools/load_sample.py --split train
python tools/validate_dataset.py
```

预期输出：第一条显示 RGB、深度和标签数组尺寸；第二条显示 `"status": "PASS"`。检查要读取约 644 MiB 数据，耗时取决于磁盘。

只获得仓库文件而尚未下载完整数据时，可以运行：

```bash
python tools/load_sample.py --root examples/mini
```

Python 用法：

```python
from tools.load_sample import load_sample
sample = load_sample(".", split="train")
rgb = sample["rgb"]                 # uint8, H×W×3
depth_m = sample["depth_m"]         # 原始深度按记录单位换算；0 为无效
part_id = sample["part_id"]         # uint8；0 背景，255 未知
policy_id = sample["policy_id"]     # 1 允许，2 不鼓励，3 禁止
```

## 下载

- 仓库：[https://github.com/HCXMr/LabVSP](https://github.com/HCXMr/LabVSP)。
- 固定版本入口：[v1.0.0 Release](https://github.com/HCXMr/LabVSP/releases/tag/v1.0.0)。
- 版本附件：`LabVSP-v1.0.0-data.tar.gz`、`LabVSP-v1.0.0-repository.zip` 和 `SHA256SUMS.txt`。

仓库包含说明、索引、工具和完整小样例；全量 `data/` 单独通过 Release 附件分发。数据包另附 6 个许可和引用文件：`LICENSE.md`、`LICENSE-DATA.txt`、`LICENSE-CODE.md`、`NOTICE.md`、`CITATION.cff` 和 `citation.bib`。下载后先核对 `SHA256SUMS.txt`，再把数据包解压到仓库根目录，确保目录为 `LabVSP/data/`，不要形成 `data/data/`。具体步骤见 [发布与下载说明](docs/PUBLISHING.md)。实际附件地址及校验和以 [distribution.json](metadata/distribution.json) 为准。

## 引用与许可

如果使用本数据集，请引用 [CITATION.cff](CITATION.cff) 或 [BibTeX](citation.bib)，并注明版本 `1.0.0`。论文未发表时引用数据集即可；当前没有论文 DOI 或数据集 DOI，不应填写占位 DOI。引用资料采用作者已有英文署名 Chengxuan Huang，并保留中文署名黄程宣。

数据、标注、相关数据元信息、展示图和数据集文档采用 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)。允许符合条款的非商业分享和修改；须署名、保留许可链接并说明修改，**不允许商业用途**。许可范围和正式文本见 [LICENSE.md](LICENSE.md) 与 [许可说明](docs/LICENSE_STATUS.md)。

`tools/` 中的软件代码及配套软件示例采用独立的 [PolyForm Noncommercial 1.0.0](LICENSE-CODE.md) 软件许可，同样限制商业用途。数据许可与软件许可分别适用。问题请通过 [GitHub Issues](https://github.com/HCXMr/LabVSP/issues) 联系维护者。

## 已知限制

- 四层标注遵循可见证据原则，不能补成不可见表面的真值；接触策略标签不是物理抓取成功标记。
- 深度为传感器观测，透明物体处可能缺失或错误，未提供独立的完整表面深度真值。
- 标签中保留 `255` 未知值，训练和评估时不能当作背景或允许接触。
- 7 张多物体图像有 8 对实例边界重叠，具体 ID 和像素数已记录；本次未修改原边界。
- 28 个实物的全部尺寸字段为空；其余两个也不完整。空值保持 `null`，不能解释为 0。
- 本数据版本通过全量结构及哈希检查，并抽查了预览图；没有完成逐图、逐边界的独立人工语义复审。

本版本数据复核见 [release_validation.json](reports/release_validation.json)；[2026-10-18 基线检查报告](reports/检查报告.md) 保留最初整理时的详细审计记录。
