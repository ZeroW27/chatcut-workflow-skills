---
name: chatcut-final-cut-compound-handoff
description: Export an approved ChatCut hard-cut A-roll and rebuild it as a new editable Final Cut Pro FCPXML/FCPXMLD while preserving an existing compound clip, synchronized audio, grades, and resources. Use only for cuts-only ChatCut-to-Final-Cut handoff.
---

# ChatCut 粗剪回挂 Final Cut

## 使用条件

只在用户已经确认 ChatCut A-roll 粗剪，并明确要求导出或回挂 Final Cut Pro 时使用。这个 Skill 不重新判断口播内容，也不添加任何画面包装。

需要：

- ChatCut 导出的 Premiere/FCP7 XMEML。
- 与代理素材对应的原始 Final Cut `.fcpxml`、`.fcpxmld` 或 `.textClipping`。
- 新输出路径。原始输入和旧输出必须保留。

如果没有对应的原始 Final Cut XML，只能生成基础单素材 FCPXML，无法承诺保留复合片段、外录音频、调色或稳定关系；执行前必须让用户明确接受这个降级。

## 执行边界

- 只迁移保留区间、源入出点、顺序和硬切时间。
- 忽略 ChatCut XML 中的缩放、位置、速度、关键帧和其他视觉运动信息。
- 不在新时间线的外层 `ref-clip` 上新增 `adjust-transform`。
- 原 Final Cut 复合片段内部已有的视频、外录音频、调色、稳定、调整层和时间关系原样保留。
- 从当前输入动态读取 `frameDuration`、格式、尺寸和时间基准；所有时间使用有理数并对齐到当前帧网格。
- 不修改 `.fcpbundle`，不覆盖输入或旧结果。生成新的输出并停在手动导入前。

## 路由

1. 先读取两个 XML 的实际结构，再选择脚本。
2. 原 Final Cut 项目时间线含一个内联 `sync-clip`：运行 `scripts/sync_chatcut_into_fcpxmld.py --cuts-only`，默认生成一个扁平复合片段资源和多个 `ref-clip`。
3. 原 Final Cut 项目已经是一个 `media` 加一个时间线 `ref-clip`：运行 `scripts/apply_chatcut_to_compound_fcpxml.py --cuts-only`。
4. 没有可回挂的原 Final Cut 复合片段、且用户接受降级：运行 `scripts/convert_xmeml_to_fcpxml.py --cuts-only`。
5. 不要凭文件名猜路由；脚本拒绝输入时先核对结构，不要绕过检查。

## 输出与验证

按 [references/validation.md](references/validation.md) 验证。至少确认：

- 新输出存在，原始输入未改变。
- 所有新时间线 cut 在当前编辑帧边界。
- 复合片段模式下，所有外层 `ref-clip` 引用同一个 `media`。
- 没有从 ChatCut 新增的 `adjust-transform`、变速或关键帧。
- 外录音频、调色和其他原复合片段内容仍在资源树中。
- XML 可解析；可用 DTD 时执行 DTD 验证。

交付新 XML/FCPXMLD 和转换报告，说明尚未进行 Final Cut 实际导入。用户偏好手动导入验收时，不打开或自动操作 Final Cut。
