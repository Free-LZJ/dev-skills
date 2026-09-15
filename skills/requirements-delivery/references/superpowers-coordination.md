# 方法协同

| 场景 | 方法 |
|---|---|
| 进入系统分析或发现会改变实现的未知项 | Plan 模式问答 |
| Bug、测试失败、运行异常或根因不清 | `systematic-debugging` |
| 完成、修复、通过或可交付前 | `verification-before-completion` |
| 交互式页面草图、视觉方案比较或空间关系讨论 | `visual-companion` 参考指南 + Codex 视觉插件 |
| 生成/解释图表、模拟或数据可视化 | `visualize` |
| 用户明确要求 `super` / `strict` 测试治理 | `$dev-test` |

只读取当前场景需要的方法文档。Plan 模式负责系统分析中的问答和决策闭合，视觉伴侣负责交互式视觉讨论，`visualize` 负责可视化结果，requirements-delivery 负责任务范围、状态和证据；不要重复创建两套报告。
