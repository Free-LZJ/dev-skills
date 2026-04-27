# exe-cloud-apps-peil 开放对象应用模式

本参考记录 `exe-cloud-apps-peil` 当前已经出现的开放对象使用方式，后续处理相似需求时先复用这些模式。

## 任务参与成员：`open_to -> p_peil_task_member`

用途：

- 任务开放范围决定哪些用户是任务参与成员。
- 结果过账到 `p_peil_task_member`。
- 该表被“我的任务”、报表、练习统计等多处 SQL 消费。

主要链路：

| 环节 | 代码 |
|------|------|
| 固定话术 Hook | `TaskHook#onOpenTargetNotify(...)` |
| 情景任务 Hook | `InterviewHook#onOpenTargetNotify(...)` |
| MQ 主题 | `Peil_Task_Member_Change_Region` |
| MQ 消费 | `TaskAssignmentListener` |
| 同步服务 | `TaskRecordValidityUpdater` |
| 结果表 | `p_peil_task_member` |

同步模式：

1. Hook 收到开放对象通知。
2. 非 `data_board_viewers` 的开放对象按现有任务成员链路发送 MQ。
3. `TaskRecordValidityUpdater` 加载任务记录。
4. 调用 `openTargetProvide.buildOpenTargetAuthUserList(task, "open_to")` 展开目标用户。
5. 查询当前 `p_peil_task_member`。
6. 新用户新增，已有失效用户置有效，不再开放的用户置无效。
7. 分片使用 `taskMemberUpdatePool`，写入和更新带 trace。

适用场景：

- 需要保留历史成员记录。
- 下游 SQL 依赖 `is_valid`。
- 授权收缩时不能物理删除历史行。

## 数据看板管理人员：`data_board_viewers -> p_peil_task_manege_member`

用途：

- 专门控制数据看板中哪些管理人员可以看到任务。
- 与任务参与成员 `open_to` 语义隔离。
- 结果过账到 `p_peil_task_manege_member`，用于列表、详情、记录、人设成员等接口的任务级权限。

主要链路：

| 环节 | 代码 |
|------|------|
| 固定话术 Hook | `TaskHook#onOpenTargetNotify(...)` |
| 情景任务 Hook | `InterviewHook#onOpenTargetNotify(...)` |
| openType 分支 | `TaskTable.DATA_BOARD_VIEWERS` / `InterviewTaskTable.DATA_BOARD_VIEWERS` |
| 内部事件 | `TaskManageMemberTable.Action.HANDLE_OPEN_TARGET_CHANGE` |
| Action | `TaskManageMemberAction` |
| 同步服务 | `DataBoardManageMemberSyncService` |
| 结果表 | `p_peil_task_manege_member` |

同步模式：

1. Hook 按 `openType` 识别 `data_board_viewers`。
2. 不走原 `open_to` MQ，改为触发内部异步事件。
3. 同步服务按 `taskType + taskId` 加分布式锁。
4. 调用 `OpenTargetProvide` 展开管理人员。
5. 查询当前结果表，计算目标集合和当前集合差异。
6. 新增和删除都按分片批量执行。
7. 结果表是精确镜像，不维护 `is_valid`。

适用场景：

- 权限结果只表示“当前可见”，不需要保留历史。
- 列表 SQL 只需要 `EXISTS` 判断当前用户是否命中。
- `ALL` 或业务“未配置默认开放”不应物化全员，避免结果表爆炸。

## 权限判断口径

数据看板当前业务口径：

| option | 行为 |
|------|------|
| `ALL` | 任务级权限直接通过 |
| 未配置 | 业务兼容为默认开放 |
| `NONE` | 任务级权限拒绝 |
| `PART` | 必须命中 `p_peil_task_manege_member` |

注意：

- 平台缺失开放对象记录默认 `NONE`，但数据看板业务要求“未配置默认开放”，两者不同。
- 直跳接口应先判断开放对象 `option`，再决定是否查结果表。
- 列表接口应在 SQL 层过滤，不能全量查任务后 Java 内存分页。
- `data_board_viewers` 是开放对象 `openType`，不要默认写成 `p_peil_task.data_board_viewers` JSON 字段。

## 代码审查清单

处理开放对象相关需求时，至少检查：

- 是否按 `openType` 分支，避免 `open_to` 和 `data_board_viewers` 混用。
- 是否存在循环内查询开放对象或结果表。
- 是否把开放对象逻辑字段误当业务表物理列。
- 是否明确 `NONE`、`ALL`、`PART` 和“未配置”的业务语义。
- 是否为高频列表建立过账表或 SQL-template 下推方案。
- 是否在结果同步中处理授权收缩。
- 是否有分布式锁、分片、批量写入和事务边界。
- 是否用表常量替代表名和字段名硬编码。
