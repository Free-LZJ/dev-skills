# 平台开放对象机制参考

## 运行机制

V4 开放对象已从旧图数据库方案调整为基于 PG 的关系型数据库实现。开放对象字段在业务层表现为 `openType`，配置和授权由平台基础对象维护。

核心存储：

| 表/对象 | 作用 |
|------|------|
| `p_base_open_target` | 开放对象主记录，保存 `biz`、`open_type`、`data_id`、`option` |
| `p_base_open_target_auth` | 授权明细，保存人员、部门、群组授权和 `scope` |
| `p_base_user_group_member` | 群组成员关系，`GROUP` 授权展开时使用 |

核心字段常量来自 `OpenTargetConstants`：

| 常量 | 字段 |
|------|------|
| `BIZ` | `biz` |
| `OPEN_TYPE` | `open_type` |
| `DATA_ID` | `data_id` |
| `OPTION` | `option` |
| `AUTH_TYPE` | `type` |
| `AUTH_ID` | `auth_id` |
| `SCOPE` | `scope` |
| `DEFAULT_OPEN_TYPE` | `open_target` |

`OpenTargetOption`：

| 枚举 | 值 | 语义 |
|------|------|------|
| `NONE` | `0` | 不开放 |
| `ALL` | `1` | 开放所有 |
| `PART` | `2` | 开放部分 |

## OpenTargetProvide

入口类：`com.exe.cloud.epaas.business.opentarget.OpenTargetProvide`

常用方法：

| 方法 | 用途 |
|------|------|
| `getUserAuthData(biz, openType, userId, condition)` | 获取当前用户可见的业务数据 ID |
| `getUserAuthDataPage(biz, openType, userId, condition, pageable)` | 分页获取当前用户可见的业务数据 ID |
| `checkDataAuth(biz, openType, userId, dataId)` | 判断当前用户是否可见某条业务数据 |
| `buildOpenTargetAuthUserList(biz, openType, dataId, condition)` | 根据业务数据 ID 展开开放人员 |
| `buildOpenTargetAuthUserList(IDataRecord bizData, openType, condition)` | 根据已加载业务数据展开开放人员 |
| `pushOpenTargetAuth(data, openType, authType, authIds)` | 添加开放对象授权 |
| `removeOpenTargetAuth(data, openType, authType, authIds)` | 移除开放对象授权 |
| `upgradeBizDataAsOpenTarget(...)` | 将历史人员/部门字段升级为开放对象 |

使用边界：

- `getUserAuthDataPage` 是列表分页首选，适合“用户能看哪些数据”。
- `buildOpenTargetAuthUserList` 是单据展开首选，适合“这条数据开放给哪些人”。
- 批量列表中循环调用 `buildOpenTargetAuthUserList` 是 N+1 风险。

## RdsOpenTargetProvide 关键行为

源码实现类：`RdsOpenTargetProvide`

授权数据查询：

- `mkBizDataQuery(...)` 会构造 `open_all`、`auth_data`、`block_data` 等查询片段。
- `open_all` 查询 `p_base_open_target`，条件包含 `biz`、`open_type`、`option=ALL`。
- `PART` 查询通过 `p_base_open_target_auth` 关联主记录，按 `USER`、`DEPT`、`GROUP` 展开。
- `BLOCK` 授权会从可见结果中排除。

人员展开：

- `buildOpenTargetAuthUserList(IDataRecord bizData, openType, ...)` 通过 `bizData.getRelativeOne(openType)` 获取开放对象关联记录。
- `buildOpenTargetAuthUserList(biz, openType, dataId, ...)` 通过 `DataLoaderManager.getOpenTargetRecordFuture(...)` 获取开放对象记录。
- `doBuildOpenTargetAuthUserList(...)` 在开放对象记录缺失时默认 `OpenTargetOption.NONE`。
- `ALL` 会查询当前租户组织下有效用户，`PART` 会按人员、部门、群组授权展开。

因此，业务如果要求“未配置默认开放”，不能直接套平台缺省语义，需要在业务权限判断中显式处理。

## 开放对象通知

入口接口：`OpenTargetNotifyHook`

```java
default void onOpenTargetNotify(ChainContext chainContext, String openType, IDataRecord data)
default void onOpenTargetSubNotify(ChainContext chainContext, String table, String openType, IDataRecord data)
```

平台组件：`OpenTargetNotifyCmp`

- 从请求变量读取 `id`、`open_type`、`payload`。
- 有 payload 时按 `biz`、`data_id`、`open_type` 加载业务数据。
- 找到 `@SPI.Service(functionName = "...")` 注册的 `OpenTargetNotifyHook`。
- 在异步线程中调用 Hook。
- 日志关键字通常包含 `open_target_notify`。

重试或调试可通过内部接口触发，路径通常是：

```text
/paas/intra/{appName}/prod/{funcName}/open_target_notify
```

变量：

```json
{
  "variables": {
    "id": "{dataId}",
    "open_type": "{openType}"
  }
}
```
