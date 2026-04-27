---
name: epaas-open-target
description: ePaaS 开放对象机制开发指南。凡是问题涉及开放对象、OpenTargetProvide、OpenTargetNotifyHook、openType、open_target、open_to、data_board_viewers、p_base_open_target、p_base_open_target_auth、开放对象权限判断、开放对象同步过账到结果表、人员/部门/群组授权展开、列表权限过滤、开放对象 N+1 优化、开放对象 SQL-template 查询，都必须优先使用本 skill。遇到 ePaaS 业务对象开放范围、任务成员同步、数据看板管理人员、权限可见数据、开放对象回调或人员异动通知时主动触发。
---

# ePaaS 开放对象

用于处理 ePaaS 开放对象的接入、查询、权限判断、变更回调、同步过账和 SQL 下推。使用时先确认运行库机制和业务默认语义，再决定走平台 API、开放对象基础表、还是业务同步结果表。

## 先读结论

- `openType` 是开放对象逻辑字段名，不要默认认为业务表存在同名物理列。
- V4 开放对象基于 PG 关系表实现，核心表是 `p_base_open_target` 和 `p_base_open_target_auth`。
- `OpenTargetOption` 语义是 `NONE=0`、`ALL=1`、`PART=2`。
- 平台 `RdsOpenTargetProvide` 在开放对象记录缺失时默认按 `NONE` 处理；如果业务要求“未配置默认开放”，必须在业务权限层显式兼容。
- 列表、报表、大数据量过滤不能循环调用 `buildOpenTargetAuthUserList(...)`；优先使用平台分页授权查询、SQL-template 下推，或同步过账后的结果表。
- 写 SQL 时必须同时使用 `$sql-template`；写 DataRecord 查询或批量处理时优先使用 `$datarecord`；写 Hook / 事件链时优先使用 `$epaas-server`。

## 决策流程

1. 先确认开放对象来源。
   - 查 BizModel 字段编码和 `openType`。
   - 依赖源码，确认当前机制是否为 V4 RDS。
   - 查业务代码是否已有过账表，例如 `p_peil_task_member`、`p_peil_task_manege_member`。

2. 再选择读取方式。
   - 单条业务数据展开人员：使用 `OpenTargetProvide.buildOpenTargetAuthUserList(...)`。
   - 当前用户可见数据列表：使用 `getUserAuthData(...)` 或 `getUserAuthDataPage(...)`。
   - 复杂列表或报表：用 SQL-template 关联开放对象基础表，或消费已同步的业务结果表。
   - 高频权限判断：优先同步过账到业务结果表，再用 `EXISTS` / 半连接判断。

3. 最后落权限语义。
   - `ALL`：直接通过，通常不要物化全员。
   - `NONE`：直接拒绝。
   - `PART`：必须命中授权展开结果或业务过账表。
   - 记录缺失或 `option` 为空：按平台默认是 `NONE`；如业务确认默认开放，必须写在业务兼容逻辑和分析文档中。

## 平台 API

常用入口：

```java
OpenTargetProvide openTargetProvide = OpenTargetProvide.getInstance();

AuthDataList data = openTargetProvide.getUserAuthData(
        biz, openType, userId, condition);

ListPageResult<String> page = openTargetProvide.getUserAuthDataPage(
        biz, openType, userId, condition, Pageable.page(pageNo, pageSize));

AuthUserList users = openTargetProvide.buildOpenTargetAuthUserList(
        bizData, openType);
```

使用规则：

- `getUserAuthData(...)` 适合“当前用户能看哪些业务数据”，不要自己逐条判断。
- `getUserAuthDataPage(...)` 适合直接分页获取授权数据 ID，再批量加载业务数据。
- `buildOpenTargetAuthUserList(...)` 适合“某条业务数据开放给哪些人”，不适合在大列表中循环调用。
- `pushOpenTargetAuth(...)` / `removeOpenTargetAuth(...)` 用于程序化维护开放对象授权。
- `upgradeBizDataAsOpenTarget(...)` 用于把历史人员/部门字段迁移为开放对象。

详细平台事实见 [platform-open-target.md](references/platform-open-target.md)。

## Hook 与人员异动

业务需要感知开放对象变更时，实现 `OpenTargetNotifyHook`：

```java
@Component
@SPI.Service(functionName = "p_demo_biz")
public class DemoOpenTargetHook implements OpenTargetNotifyHook {
    @Override
    public void onOpenTargetNotify(ChainContext ctx, String openType, IDataRecord data) {
        if (!"open_to".equals(openType)) {
            return;
        }
        // 触发业务同步或权限结果刷新
    }
}
```

注意：

- 一个业务对象可以有多个开放对象字段，必须用 `openType` 分支，禁止把所有开放对象变更混成一条链。
- 通知在平台异步线程中执行，业务要自己处理幂等、重试、日志和一致性。
- 高频或耗时同步不要直接在 Hook 中逐条落库；应转内部事件、MQ 或专用异步服务。
- 子表开放对象使用 `onOpenTargetSubNotify(...)`。

## 同步过账模式

当开放对象结果要支撑列表过滤、报表统计、直跳权限或多接口复用时，优先把 `PART` 展开的人员集合过账到业务结果表。

推荐结构：

| 字段 | 用途 |
|------|------|
| `task_id` / `data_id` | 来源业务数据 ID |
| `task_type` / `biz_type` | 区分多来源业务 |
| `user_id` | 展开后的可见人员 |
| `source` / `source_id` | 可选，区分开放对象、导入或其他来源 |
| `is_valid` | 可选，适合需要保留历史记录的过账表 |

实现要求：

- 用 `buildOpenTargetAuthUserList(data, openType)` 或等价开放对象读取方式得到目标人员集合。
- 先批量查询当前结果表，再做差量新增、删除或置失效。
- 使用分布式锁按业务数据维度串行化同一对象同步。
- 大集合按 1000 左右分片，批量 `merge` / `batchDirectMerge`，不要循环单条查写。
- `ALL` 通常只清空结果表，不物化全员；`NONE` 和 `PART` 空集合都应收敛为空结果。
- 线程池分片时，每个分片要有独立事务边界，主流程只做差异计算和等待。

当前项目案例见 [peil-patterns.md](references/peil-patterns.md)。

## 权限判断模式

直跳详情或操作权限：

1. 读取开放对象 `option`，来源必须是开放对象记录、平台 API 或已确认的关联数据。
2. `ALL` 直接通过。
3. `NONE` 直接拒绝。
4. `PART` 查询过账表是否存在当前用户。
5. 业务要求“未配置默认开放”时，在第 1 步后显式把缺失记录映射为 `ALL`。

列表或报表权限：

- 不要先查全量业务数据再内存过滤分页。
- 优先 `getUserAuthDataPage(...)` 或 SQL-template 下推。
- 如果业务已有过账表，列表 SQL 用 `EXISTS` 命中过账表。
- 如果必须关联开放对象基础表，按 `biz + open_type + data_id` 关联 `p_base_open_target`，再用 `option` 和 `p_base_open_target_auth` 或过账表判断。
- 禁止写成 `t.<openType>` 或 `t.<openType>::jsonb ->> 'option'`，除非已经用源码和运行库确认该业务表确实存有同名物理列。

## SQL 注意事项

写开放对象 SQL 时：

- 先用 `OpenTargetConstants` 或源码确认字段名：`biz`、`open_type`、`data_id`、`option`、`auth_id`、`type`、`scope`。
- 业务数据主键和开放对象 `data_id` 类型可能不同，PG 中经常需要显式类型转换。
- `UNION ALL` 时每个分支列类型必须对齐。
- 用户输入、关键词、当前用户、分页参数必须走 `SqlTemplate` 参数，不要拼接。
- 如果业务默认语义和平台默认语义不同，在 SQL 中用 `LEFT JOIN` + `COALESCE` / `CASE` 明确表达。

## 常见陷阱

- 把开放对象字段当成业务表 JSON 字段读取。
- 在任务列表中对每条任务调用 `buildOpenTargetAuthUserList(...)`，引入 N+1。
- 把平台“缺失开放对象默认 NONE”误用到业务“未配置默认开放”的场景。
- `ALL` 场景物化全员，导致结果表爆炸。
- Hook 未按 `openType` 分支，导致 `open_to` 和 `data_board_viewers` 互相污染。
- 过账表同步只新增不删除，导致授权收缩后权限残留。
- 线程池分片共用主事务，造成事务边界和异常回滚不可控。
