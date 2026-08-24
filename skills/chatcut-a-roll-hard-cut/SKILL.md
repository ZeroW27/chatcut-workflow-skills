---
name: chatcut-a-roll-hard-cut
description: Edit a talking-head A-roll in ChatCut from a transcript or outline using content-only hard cuts. Use for retake cleanup and natural speech boundaries; do not use for visual packaging or XML export.
---

# 口播 A-roll 纯硬切

## 目标

在 ChatCut 中完成可复核的口播 A-roll 粗剪。只决定保留什么和在哪里硬切；所有画面包装留到 Final Cut Pro。

## 输入

- 当前 ChatCut 项目中的口播视频。
- 逐字稿或拍摄大纲。先判断参考文件类型，不要把大纲当逐字稿。

## 剪辑规则

- 逐字稿按语义对应，不要求逐字一致。
- 大纲只约束主题和结构；保留相关的完整发挥、解释、例子和新增观点。
- 同一内容有多个 take 时，保留最后一个完整自然的版本；若最后一遍不完整，改选更完整的一遍。
- 删除口误、NG、重复尝试、废弃开头和无意义残句。不要拼接不同 take 的残句。
- 通过 Script 完成语义选择，再检查实际切口，不能只相信转写分段边界。
- 每个保留片段在第一个清晰音素前保留原素材中的 5–8 帧；整条视频开头保留 8–12 帧。原素材不足时只保留实际存在的气口，不创造黑场或静音。
- 等句尾尾音或气声真正结束后再保留 3–5 帧；不要切死尾音，也不要留下过长尾段。

## 严格边界

- 全部保持原速、100% 原始构图。
- 不添加缩放、位移、关键帧、缓推、变速、转场、B-roll、字幕、音乐或其他包装。
- 不导出 XML，不修改 Final Cut 文件，也不自动启动后续交接流程。

## 完成检查

- 对照逐字稿或大纲复核：没有误删有效新增内容，也没有留下重复 take 或 NG。
- 试听开头、中间和结尾的代表性切口：起音自然、尾音完整、无意外黑场。
- 确认所有 A-roll 片段仍为原速、100% 构图且没有新增视觉效果。
- 把可编辑时间线交给用户复核，然后停止。只有用户明确确认并要求进入 Final Cut 时，才使用 `chatcut-final-cut-compound-handoff`。
