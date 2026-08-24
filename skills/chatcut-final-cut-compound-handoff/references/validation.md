# Cuts-only FCPXML 验证

## 基础检查

从 Skill 目录运行：

```bash
PYTHONPYCACHEPREFIX=/tmp/video-editing-pycache python3 -m py_compile scripts/*.py
xmllint --noout "/path/to/output.fcpxmld/Info.fcpxml"
python3 -B scripts/validate_fcpxml_handoff.py \
  --input "/path/to/output.fcpxmld" \
  --expect-cuts-only
```

如果当前 Final Cut FCPXML DTD 可用，再运行对应版本的 DTD 验证。DTD 通过不等于 Final Cut 实际导入通过。

## 必查结果

- 输出路径是新的，输入和 `.fcpbundle` 未修改。
- 新项目片段数量和转换报告一致。
- `offset`、`start`、`duration` 均落在项目当前 `frameDuration` 网格。
- 复合片段模式下，时间线 cut 都是 `ref-clip`，并引用同一 `media`。
- 新时间线 cut 下没有 `adjust-transform`、时间重映射或关键帧动画。
- 不把 `format` 或 `tcFormat` 写到 `ref-clip`。
- 媒体路径保持原样；报告存在性，但不要自行重链接或猜路径。
- 抽查开头、中间、结尾 cut 的源范围和连续时间线位置。

## 手动验收边界

静态验证完成后交给用户手动导入 Final Cut Pro。实际导入后仍需检查音画同步、复合片段可编辑性、调色/稳定/外录音频是否生效。未手动导入前不得声称 Final Cut 已完全验收。
