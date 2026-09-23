# 作者仓库与框架脉络：`nick-yangzj` 的 11 个仓库

> 动机：`nick-yangzj` 是 [亿马联盟（EMA）发行链与 SDK](emagroup发行链与SDK.md) 一文里那条侧信道的来源（`MyMatch1` 带 EMA SDK 与 `cdn.emagroup.cn` 配置）。既然他曾从 EMA 渠道角度写客户端，就有必要把他的**全部仓库**过一遍，确认有没有漏掉的服务端代码或其它一手资料。
>
> **结论先说**：**没有**。11 个仓库里与本项目相关的只有 `MyMatch1` 一个；其余是 4 个未改动的框架镜像、4 个空仓库/占位、1 个博客、1 个 2024 年的图形实验。本文同时**更正**上一份文档的一处错误（他的框架作者身份），并记录顺带发现的目标包协议角色体系。

---

## 1. 仓库清单（全部 11 个）

按创建时间倒序。`fork` 一列标注父仓库；`pushed` 与父仓库 HEAD 相同者为**未改动镜像**。

| 仓库 | fork 自 | 语言 | ★ | 创建 | 最后推送 | 体积 | 结论 |
|---|---|---|---:|---|---:|---:|---|
| `RenderFeature_FOV` | — | C# | 1 | 2024-06-28 | 2024-06-28 | 34 KB | Unity URP 图形实验（见 §3） |
| `ET` | `egametang/ET` | C# | 0（父 9,916） | 2018-12-26 | 2018-12-26 | 87 MB | **未改动镜像** |
| `learntGit` | — | — | 0 | 2018-09-03 | 2018-09-03 | 1 KB | Git 练习，空 |
| `Scut` | `ScutGame/Scut` | C# | 0（父 1,340） | 2016-09-27 | 2016-07-02 | 814 MB | **未改动镜像** |
| `MyMatch1` | — | C# | 0 | 2016-06-29 | 2016-06-29 | 153 MB | **唯一与 EMA 相关**（Unity 三消） |
| `Scut-samples` | `ScutGame/Scut-samples` | C# | 0（父 62） | 2016-09-27 | 2015-11-27 | 196 MB | **未改动镜像** |
| `KeroroJinShanYunSdk` | — | — | 0 | 2015-08-05 | 2015-08-05 | 148 KB | 只有 1 张 PNG，无代码 |
| `MyTest` | — | — | 0 | 2015-03-31 | 2015-03-31 | 120 KB | 只有空 `README.md` |
| `nick-yangzj.github.io` | — | JavaScript | 0 | 2014-11-10 | 2014-11-11 | 1.7 MB | 个人博客 |
| `first-ios-game` | — | — | 0 | 2014-07-10 | 2014-07-10 | **0** | 空仓库 |
| `Cocos2DBookSource` | `zilongshanren/Cocos2DBookSource` | Objective-C | 0（父 109） | 2014-03-07 | 2013-12-22 | 50 MB | **未改动镜像**（《Cocos2D 权威指南》随书源码） |

**判定 fork 是否含自有改动的方法**：比较 fork 与父仓库的 `pushed_at`。四个 fork 的值与各自父仓库最后一次推送**完全相同**（`Scut` 2016-07-02、`Scut-samples` 2015-11-27、`Cocos2DBookSource` 2013-12-22、`ET` 停在 2018-12-26 而父仓库至今仍在更新）。fork 出来只是把父仓库的分支原样复制，此后无任何推送，因此**这些 fork 里不存在公司代码**。

---

## 2. 学习轨迹（这是清单里唯一有信息量的模式）

四个 fork 的**创建时间**串成一条清晰的自学路线，与其自有项目的时间线也吻合：

```
2013-12  Cocos2DBookSource      《Cocos2D 权威指南》随书源码   ─┐ 客户端入门
2014-07  first-ios-game（空）                                  ─┘
2015-03  MyTest（空）
2015-08  KeroroJinShanYunSdk（截图）                           ── 金山云 SDK 接入
2016-06  MyMatch1                Unity + C# + Lua 三消         ── 首个完整项目（带 EMA SDK）
2016-09  Scut / Scut-samples     游戏服务端框架                ─┐ 转向服务端
2018-09  learntGit（空）                                       ─┘
2018-12  ET                      Unity3D 客户端 + C# 服务端双端 ── 双端框架
2024-06  RenderFeature_FOV       Unity URP RenderFeature       ── 图形方向
```

即：**Cocos2D 客户端 → 服务端框架（Scut）→ Unity 双端（ET）→ 图形渲染**。这条轨迹解释了 MyMatch1 为什么是「Unity 客户端 + C#/Lua 双端 + 自带 socket 层」的形态——它在时间上正好夹在 Scut 与 ET 之间。

**但要注意 MyMatch1 的网络层并非来自 Scut**：`Scut` 仓库的 1,575 个 blob 中**没有** `SocketClient.cs` / `Protocal.cs` / `ByteBuffer.cs` 等同名文件（已用递归树逐一比对）。MyMatch1 的 `NetWorkManager`（2 字节大端长度 + `int16 mainId`，`Protocal.Connect=101`）是中文 Unity 圈里常见的教学式 socket 实现，与 Scut 无文件级继承关系。

---

## 3. 自有仓库逐个说明

| 仓库 | 内容 | 与本项目的关系 |
|---|---|---|
| `MyMatch1` | Unity 5.3.4f1，productName「我的三消」，`com.nickyangzj.sanxiao`，companyName `Mius`；带 EMA Android SDK 的 Unity 包装 + `cdn.emagroup.cn/mymatch/android/VerInfo.txt` | **唯一相关**。详见 [亿马联盟（EMA）发行链与 SDK](emagroup发行链与SDK.md) |
| `KeroroJinShanYunSdk` | 全仓库**只有 1 个文件**：`屏幕快照 2014-04-10 上午11.16.02.png`。仓库名指向「Keroro 项目 + 金山云 SDK 接入」 | 无代码。仅能说明 2015 年前后在接金山云（`JinShanYun`）SDK |
| `MyTest` | 全仓库**只有 1 个文件**：空白的 `README.md` | 无 |
| `learntGit` / `first-ios-game` | 空白 | 无 |
| `nick-yangzj.github.io` | 个人博客源码（2014） | 无。年代早于三款游戏 |
| `RenderFeature_FOV` | Unity **URP** 实验：`Assets/_Scripts/{CameraFovRenderFeature,CameraFovRenderPass,RenderManager}.cs` + `URPSettings/SampeURP_Renderer.asset`，默认分支 `main`，含 Unity 2022 的 `UserSettings/Layouts/default-2022.dwlt` | 无。2024 年个人图形技术验证 |

`KeroroJinShanYunSdk` 的仓库名间接提供了一个旁证：他 2015 年接触过 **Keroro（青蛙军曹）** 题材项目。`MyMatch1` 的 `Assets/Keroro.prefab` 与之一致——但两处都只是个人项目里的素材引用，**不能**据此认定它属于 EMA 的哪个商业产品。

---

## 4. 与三款目标游戏的关系：无代码级关联

| 检查项 | 结果 |
|---|---|
| 仓库中有 EMA 服务端 / 三款目标游戏代码吗？ | **没有**。11 个仓库全部检查过，`MyMatch1` 是唯一带 EMA 痕迹的 |
| 四个框架镜像里有公司代码吗？ | **没有**。`pushed_at` 与父仓库 HEAD 一致，未提交任何改动 |
| `Scut` / `ET` 能解释目标包的服务端吗？ | **不能直接解释**。见下 |
| `MyMatch1` 与目标包共用代码吗？ | **不共用**。命中仅有 `GameContinue`/`GameExit`/`DoQuitSdk`/`ResetPay`/`GameInfo` 这批 **EMA 原生 Java SDK 的 API 名**，C# 包装类名（`SDKEMAController` 等）全为 0 命中 |

顺带排除一个**假阳性**（记录下来避免以后重犯）：对目标包原生库做子串搜索时，`enet` 会命中 `BattleNetworkInput` 里的 "eNet"、`kcp` 会命中随机串 `kcpl|n|;`（`Select-String -SimpleMatch` 默认大小写不敏感，加剧了误报）。**三个包里没有 ENet，也没有 KCP。** 目标包的序列化确实是 protobuf，且是 **proto2**（库内保留 `".  This parser only recognizes "proto2".`），与 `Scut`/`ET` 无标识关联。

---

## 5. 顺带发现：目标包的协议角色体系（`a` / `g` / `c`）

既然是去查"服务端框架"，就有了一个直接收获——**客户端二进制本身透露了服务端拓扑**。

在 `ciyuan_2017/proto_schema_recovered.json` 恢复出的 **142 个 protobuf 消息**里，有 18 个带方向标记，其中 10 个属于网络层，形成一套严格的 `S<源>2<目标><Req|Ack|Notify><动作>` 命名：

| 方向 | 消息 |
|---|---|
| `c` → `g` | `Sc2gReqClientLogin` |
| `g` → `c` | `Sg2cAckClientLogin`、`Sg2cErrorInfo`、`Sg2cSecretKey` |
| `g` → `a` | `Sg2aReqClientLogin`、`Sg2aAckExchange`、`Sg2aAckSendItem`、`Sg2aAckSendAtrrItemExchange`、`Sg2aAckSendStatusHero`、`Sg2aUserLogout` |
| `a` → `g` | `Sa2gAckClientLogin`、`Sa2gErrorInfo`、`Sa2gLoginTypeNotJumpw`、`Sa2gNotifyGameGUID`、`Sa2gReqExchange`、`Sa2gReqSendItem`、`Sa2gReqSendAtrrItemExchange`、`Sa2gReqSendStatusHero` |

**推断的登录链**（三个角色 `c`=客户端、`g`=游戏服、`a`=账号/发货服）：

```
c ──Sc2gReqClientLogin──▶ g
                          g ──Sg2aReqClientLogin──▶ a
                          g ◀──Sa2gAckClientLogin── a   (+ Sa2gLoginTypeNotJumpw)
c ◀──Sg2cAckClientLogin── g   (+ Sg2cSecretKey)
```

三点可读出的信息：

1. **客户端不直连账号服**——登录必须由游戏服 `g` 中转，客户端只跟 `g` 对话。这与"权威服务器"的结论一致（客户端不持有账号态）。
2. **`a` 兼做发货**：`Sa2gReqSendItem` / `Sa2gReqSendAtrrItemExchange` / `Sa2gReqExchange` / `Sa2gReqSendStatusHero` 说明 `a` 不只是校验登录，还向 `g` 下发物品、兑换与英雄状态——即**平台充值发货通道**。与 EMA/Jumpw SDK 侧（§[发行链文档](emagroup发行链与SDK.md)）的支付链路对得上。
3. **服务间（`a`↔`g`）的消息定义被编译进了客户端**——说明客户端与服务端**共用同一份 `.proto`**，这也解释了为什么客户端的 `k*FieldNumber` 能完整恢复出 schema。

另有一组与战斗连接相关、且已暴露到 Lua 的符号：

```
_ZN18BattleNetworkInput11OnConnectedEv          GetBattleNetworkInput()
_ZN18BattleNetworkInput7SendMsgEP3Msg           TryConnectOrClose()
_ZN18BattleNetworkInput23UseBattleConnectSendMsgEPK3Msg
Script_IsBattleConnected / C_IsBattleConnected
```

即战斗连接是一个**独立于大厅连接的会话对象**，且 Lua 层可直接查询连接状态（`Script_IsBattleConnected`）——与「进入战斗时切换连接」的设计吻合。

> 以上角色语义是**从命名与字段推断**的，不是从服务端代码读到的。`a` 的确切含义（account / activity / admin）尚无直接证据，标注为未定。

---

## 6. 对本项目文档的更正

[亿马联盟（EMA）发行链与 SDK](emagroup发行链与SDK.md) 初版 §1 写过「`nick-yangzj` 是知名开源游戏服务器框架 Scut 与 ET 的作者」——**这是错的**，他这两个仓库都是 `fork=true` 的未改动镜像。该处已就地更正。

出错原因：`GET /users/nick-yangzj/repos` 的列表接口不返回 `fork` 字段信息时容易只看到「仓库名 = 框架名」，需要额外取 `/repos/{owner}/{repo}` 才能看到 `fork`/`parent`/`source`。这也是本文把 fork 判定方法写进 §1 的原因。

---

## 7. 复现方法

```bash
U=https://api.github.com/users/nick-yangzj/repos?per_page=100&sort=pushed

# 1) 列表：注意此接口不含 fork 判定
curl -s "$U" | python -c "import json,sys;[print(r['name'],r['language'],r['size'],r['created_at'],r['pushed_at']) for r in json.load(sys.stdin)]"

# 2) 逐个确认 fork 与父仓库（关键一步）
for r in Scut ET Scut-samples Cocos2DBookSource; do
  curl -s "https://api.github.com/repos/nick-yangzj/$r" \
    | python -c "import json,sys;d=json.load(sys.stdin);print(d['name'],'fork=',d['fork'],'parent=',d['parent']['full_name'],'fork_pushed=',d['pushed_at'],'parent_pushed=',d['parent']['pushed_at'])"
done

# 3) 空仓库/占位仓库的内容
for r in KeroroJinShanYunSdk MyTest; do
  curl -s "https://api.github.com/repos/nick-yangzj/$r/git/trees/master?recursive=1" \
    | python -c "import json,sys;[print(t['path']) for t in json.load(sys.stdin)['tree']]"
done

# 4) 排除"网络层来自 Scut"的假设
curl -s "https://api.github.com/repos/nick-yangzj/Scut/git/trees/master?recursive=1" \
  | grep -E 'SocketClient\.cs|Protocal\.cs|ByteBuffer\.cs'   # 无输出 = 无关
```

本文用到的目标包侧证据（需先跑完主流水线）：

```bash
python apk_analysis/inspect_proto_schema.py ciyuan_2017   # → ciyuan_2017/proto_schema_recovered.json
```
