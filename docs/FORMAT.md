# 文件、标注和索引格式

本说明适用于 `labvsp.manifest.v1`。所有发布索引使用相对路径，基准是仓库根目录。图像 ID 与实例 ID 可包含 `__`，不依赖当前机器的目录结构。

## 索引对应关系

- `metadata/manifest.json` 中 `images` 一行对应一张 RGB-D 图像，`records` 一行对应图像里的一个器皿实例。
- `image_id` 由原始 `single/multi + session_id + scene_id` 稳定组合。`sample_id` 再加上 `object_id`。
- `object_id` 是实体器皿编号，跨图像保持不变；不是图像内实例排序号。
- `split` 是图像角色；`object_role` 是原始实物角色。`multi_test` 中实物的 `object_role` 仍为 `train`。
- `metadata/images.jsonl`、`instances.jsonl` 分别与主清单的 `images`、`records` 对应；每行独立 JSON。
- `splits/*.txt` 每行是 `image_id`，不是文件名。通过 `manifest.json` 查询 RGB 等文件。
- `metadata/files.jsonl` 记录 `data/` 的每个文件、字节数、SHA-256。元数据和文档不混入数据载荷清单。

## 图像与深度

| 路径 | 格式 | 解释 |
|---|---|---|
| `data/rgb/<image_id>.png` | RGB uint8，480×640×3 | 原始彩色图像 |
| `data/depth/<image_id>.png` | 单通道 16 位 PNG | 原始对齐深度；0 为无效 |
| `data/depth_valid/<image_id>.png` | 二值 PNG | `raw_depth > 0`，不代表数值准确 |
| `data/camera/<image_id>.json` | JSON | 每帧 K/D/R/P、尺寸、单位、时间戳与对齐声明 |
| `data/scenes/<image_id>.json` | JSON | 采集条件、会话、视角等科学字段 |

当前所有深度记录的 `depth_scale_m_per_unit=0.001`，换算为 `depth_m = depth_raw × scale`。文件本身经 PNG 头检查为 16 位灰度；部分 Pillow 版本会读为 `int32`，示例读取器显式转回 `uint16`。不能把读取器的 dtype 当作原文件位深。

多物体相机记录明确写明单位并未经过传感器级独立验证；单物体记录也没有给出独立验证凭据。RGB-D 时间差范围约为 0–67.27 ms。对静态器皿和运动场景的影响不同，不应从静态数据推断动态同步精度。原相机字段完整保留。

`scenes` 仅保留采集信息。源文件中采集时的 `not_annotated`、`training_ready=false` 等旧状态没有被冒充当前状态；已有复核记录单独放在实例的 `historical_review` 中。本次结构检查见 `reports/validation.json`。

## 每个实例的四层标注

路径：`data/annotations/<image_id>/<object_id>/`。全部标签与全幅 RGB 对齐。

| 文件 / 子目录 | 编码与用途 |
|---|---|
| `instance_mask.png` | 二值实例，`>0` 为当前器皿；包括透明轮廓内部 |
| `visible_parts/*.png` | 9 种可见部位的独立二值掩码，允许跨部位重叠 |
| `functional_regions/*.png` | 4 种功能区域的独立二值掩码，与部位层独立 |
| `contact_policy_id.png` | 1=allowed，2=discouraged，3=forbidden，255=实例内未知，0=背景 |
| `structural_part_id.png` | 从独立可见部位按规定优先级折叠的单通道 ID 图 |
| `confidence_f32.npy` | float32，已知人工策略位置为 1，其余为 0 |
| `provenance_id.png` | 1=人工直接策略标注，255=实例内未知，0=背景 |
| `annotation.json` | 可见性、原始实例信息、历史复核记录；引用根目录标签字典 |

`confidence_f32.npy` 不是连续可靠性评分，不是深度置信度，也不是抓取成功概率。

## 部位字典

| 数据 ID | 名称 | 中文 | 当前 PartPolicyNet 索引 |
|---:|---|---|---:|
| 1 | body | 主体 | 0 |
| 2 | rim | 口沿 | 1 |
| 3 | inner_surface | 内表面 | 2 |
| 4 | base | 底部 | 3 |
| 5 | spout | 导流嘴 | 4 |
| 6 | handle | 把手，本稿无正像素 | 不支持 |
| 7 | neck | 颈部 | 5 |
| 8 | cap_or_stop | 盖或塞 | 6 |
| 9 | shoulder | 肩部 | 7 |

0 是背景，255 是未知。部位数据 ID 不能直接减 1 作为八类网络索引；要使用 `metadata/model_label_mapping.json`。该映射只说明当前网络接口，原始数据仍保留完整 9 类字典。

折叠时从低到高覆盖：`body → base → shoulder → neck → inner_surface → rim → spout → cap_or_stop → handle`。独立二值掩码保留重叠；不能用折叠图逆向恢复全部独立掩码。

功能区域为 `scale_print`（刻度）、`logo_or_text`（标识/文字）、`pouring_region`（倾倒区域）、`sealing_region`（密封区域）。独立文件为权威数据，预览只展示其叠加效果。

原字典颜色字段为 `color_bgr`；使用 RGB 绘图库时应反序为 RGB。未知在预览中显示灰色。数据 ID 与显示颜色无关。

## COCO 索引

`metadata/coco/{train,val,test,multi_test}.json` 描述器皿实例分割，`file_name` 相对仓库根目录。每个标注记录增加了 `labvsp_sample_id` 和 `physical_object_id`，便于回到原生四层标注。

分割采用未压缩 COCO RLE：`size=[H,W]`，按列优先展开，`counts` 从背景长度开始；`area` 为实例正像素数，`bbox=[x,y,w,h]`。需要压缩 RLE 的库可以调用 `pycocotools.mask.frPyObjects` 转换。导出器已对全部 419 个实例执行编码—解码逐像素一致性检查。

不把重叠实例强行合成一个互斥 ID 图，也不把功能区域折叠为 COCO 器皿类别。COCO 只补充通用实例接口。

## 原始来源与排除项

原 RGB、深度、有效掩码、四层标签、折叠图、confidence、provenance、camera JSON 均为独立字节副本，无缩放和重新编码。元数据去掉本机绝对路径和个人账号，保留对象编号与科学字段；本机详细对应关系保存在被 Git 忽略的 `_local/`。

历史标注备份、ROS 录制包、模型权重、MaskDINO/TDCNet 预测、训练缓存与机器人运行文件不属于这个数据发布包。此处是 RGB-D 和人工监督数据集；仅凭该包不能复现模型训练的全部前端预测与权重。
