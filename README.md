# ciyuan-moba

对三款已停运的国产 MOBA 手游做**纯静态逆向分析**：定位并复现其自定义资源封装，全量还原游戏资源，导出配置表结构，并留下可复查的脚本与证据链。

最核心的产出是一条完整可复现的链路：

```
APK → ZIP 解包 → 识别 "MP:" 自定义封装 → 定位原生库中的密钥 → XOR + zlib 还原
    → 28,629 个资源 100% 还原（0 失败）→ protobuf 配置表解析
```

> ⚠️ **本仓库只收录分析脚本、元数据报告与结论，不包含任何游戏素材或原始二进制。** 详见文末[免责声明](#免责声明)。

---

## 分析对象

| 游戏 | 包名 | 版本 | APK 大小 | ZIP 条目 | Lua 脚本 | 成品 |
|---|---|---:|---:|---:|---:|---|
| 魔霸之王（2016） | `cn.emagroup.kom.baidu` | 1.20 / 1020 | 147.6 MiB | 5,138 | 79 | `apk_analysis/moba_2016/` |
| 次元大作战（2017） | `com.emagroup.mbzw2.emagroup` | 2.16 / 201602 | 217.1 MiB | 6,185 | 165 | `apk_analysis/ciyuan_2017/` |
| 300大作战（2018） | `com.jumpw.mobile300` | 1.33 / 1303 | 443.8 MiB | 19,283 | 546 | `apk_analysis/game300_2018/` |

年份取自原始 APK 文件名，**是构建时间而非产品首发时间**。三包同为 **Snake 自研 3D 引擎 + Cocos2d-x 2D/UI 层 + Lua 5.1 / LuaJIT 2.0.1 + FMOD** 架构（引擎身份见[引擎与平台身份](apk_analysis/引擎与平台身份.md)），主入口类都是 `Tombird`，核心原生库为 `libtombird.so`（2016）与 `libgame.so`（2017 / 2018）。

**产品线关系**：《魔霸之王》(2016) 与《次元大作战》(2017) 是同一条产品线的两代——后者的包名 `com.emagroup.mbzw2.emagroup` 中 `mbzw2` 即"魔霸之王2"，二者由**亿马联盟（EMA，上海）**发行，主入口类同为 `Tombird`，资源也高度重合（1,704 个文件内容完全相同）。《300大作战》(2018) 则是 Jumpw 的产品，仅在引擎与资源上沿袭。三包签名证书互不相同。

这条产品线关系还有一条**官网级的外部证据**（见[网络存档检索](apk_analysis/网络存档检索.md)）：`www.kingofmoba.com` **同一个域名依次挂过三代产品名**——至 2016-06 是《魔霸之王》官网，**2016-08 换成《魔霸之王2》**，**2016-11 起改名《次元大作战》**并一直用到 2019-10。这与包名里的 `mbzw2` 完全咬合，也说明"次元大作战"这个名字从 2016-11 就在用。该站首页的安卓下载按钮指向官方包 `download.emagroup.cn/cydzz/packages/CY_emagroup.apk`（`CY` = 次元），同目录另有渠道包 `CY_wmagroup.apk`——**两个包 Wayback 都只记录到 404，未能抓到**。

发行链的更多内部证据——EMA SDK 的两代演进、`kom → moba02 → ciyuan` 的 CDN 代号链，以及三包共用的 Jumpw 账号/支付接入层——整理在 **[亿马联盟（EMA）发行链与 SDK](apk_analysis/emagroup发行链与SDK.md)**。

---

## 核心发现：`MP:` 资源封装格式

APK 里绝大多数游戏资源的文件头不是扩展名对应的标准头，而是 `4D 50 3A`（`MP:`）。通过反汇编原生库中的 `cocos2d::CCFileUtils::checkFileCompress`，确认其完整布局：

| 偏移 | 长度 | 内容 |
|---:|---:|---|
| 0 | 3 | 魔数 `"MP:"`（`4D 50 3A`） |
| 3 | 1 | 版本号：2016 包 = `0`，2017 / 2018 包 = `1` |
| 4 | 4 | `uint32` 小端，解压后长度 |
| 8 | 4 | 固定标记 `65 3B 39 01` |
| 12 | N | 循环 XOR 加密的 zlib deflate 流 |

还原算法：

```python
key   = b"2c596277db0fad6d6997bc80bf76a89f"   # 32 字节 ASCII，硬编码于 libgame.so / libtombird.so
plain = zlib.decompress(bytes(c ^ key[i % len(key)] for i, c in enumerate(data[12:])))
assert len(plain) == int.from_bytes(data[4:8], "little")
```

密钥不是猜出来的，而是从 ELF 里按 PC 相对引用定位到 `checkFileCompress` 内部加载的字符串常量（见 `decode_resources.py` 中 `key_addr = 0x6d21fc + *(0x6d238c)`）。

**同一把密钥对三个包全部有效**，不随版本 / 渠道变化：

| 游戏 | `MP:` 封装文件 | 未封装资源 | 还原后资源总数 | 失败 |
|---|---:|---:|---:|---:|
| 魔霸之王（2016） | 3,985 | 30 | 4,015 | **0** |
| 次元大作战（2017） | 5,923 | 94 | 6,017 | **0** |
| 300大作战（2018） | 18,721 | 14 | 18,735 | **0** |
| **合计** | **28,629** | 138 | **28,767** | **0** |

每个文件都校验了 zlib 流完整性（`eof` 且无 trailing data）与解压长度是否等于头部声明值。

### 还原之后还有第二层：protobuf 配置表

`assets/data/conf/*_c.dat` 解出来仍是二进制——它们是 **protobuf 线格式**的数值配置表。只有 2018 包附带 50 个 `.proto` 结构定义。

**但 2018 的 `.proto` 不能用来解析 2017 的数据。** 客户端原生库里编译进了 protobuf 为每个字段生成的 `k*FieldNumber` 常量，其值就是字段号——即**客户端二进制本身就是一份完整 schema 文档**。`inspect_proto_schema.py` 从 `ciyuan_2017` 的符号表恢复了 **142 个消息 / 1263 个字段号**（0 未解析），并与 2018 的 `.proto` 逐字段交叉验证：

| 结果 | 数量 |
|---|---:|
| 共有消息 | 76 |
| 字段号完全一致 | **815** |
| 字段号冲突（同名不同号） | **22** |
| 仅 2017 客户端存在 | 68 |

815 个一致验证了方法正确；而 22 个冲突是真实的版本间重排——**整张 `SItem_Item` 表在 2018 被重新编号**（`strItemName` 23→2、`nItemType` 44→9、`nSell` 48→7…）。若用 2018 的 `.proto` 解析 2017 的 `item_item_c.dat`，字段与数值会系统性错配且**不会报错**。正确做法是使用 2017 自身的字段号（`proto_schema_recovered.json`）。

`inspect_decoded.py` 已解析出英雄表与本地化字符串表：2016 → 21 条英雄记录，2017 → 35 条，2018 → 43 条。

---

## 分析流水线

按顺序执行，依赖 `cryptography`、`capstone`、`Pillow`（Python 3.11）：

| # | 脚本 | 作用 | 主要产物 |
|---:|---|---|---|
| 1 | `inspect_archives.py` | 校验 ZIP 路径安全性（绝对路径 / `..` / 反斜杠 / 冒号）并逐条读取触发 CRC 校验，计算 SHA-256 | `inventory.json` |
| 2 | `analyze_static.py` | 自实现二进制 AXML / ARSC 解析器解出可读清单与资源表；提取 DEX 类名与字符串、ELF 段与符号、全部 URL | `AndroidManifest.decoded.xml`、`summary.json`、`resources.json`、`network_strings.json` |
| 3 | `inspect_native.py` | 用 capstone 反汇编原生库指定符号，自动解析 `bl` 目标符号名 | `checkFileCompress.disasm.txt` |
| 4 | `decode_resources.py` | 从原生库动态定位密钥，复现 `MP:` 解密，全量还原 `assets/`，并做解密后跨包比对 | `decoded/`、`decoded_inventory.json`、`decoded_comparison.json` |
| 5 | `inspect_decoded.py` | 在还原结果上解析 protobuf（英雄表 / 字符串表）、`version.json`、联网引用；合成图标预览图 | `heroes.json`、`localized_strings.json`、`decoded_network_references.json`、`decoded_findings.json` |
| 6 | `inspect_proto_schema.py` | 从原生库的 `k*FieldNumber` 常量恢复 protobuf schema（字段号），并与 2018 的 `.proto` 交叉验证；三个包各跑一次 | `{slug}/proto_schema_recovered.json`、`proto_schema_crosscheck_{slug}.json` |
| 7 | `decode_config_tables.py` | 用恢复出的 schema 解码 `conf/*_c.dat` 配置表（元素消息名由表名归一化匹配推出） | 终端输出（可选导出 JSON/CSV） |
| 8 | `analyze_attributes.py` | 从配置表中文标签恢复属性 ID 枚举；审计伤害公式字段的填充情况与战力权重 | `attribute_enum.json`、`damage_inputs.json` |
| 9 | `write_report.py` | 汇总上述 JSON 生成完整中文报告 | [`apk_analysis/分析报告.md`](apk_analysis/分析报告.md) |

### 复现步骤

把三个原始 APK 放回仓库根目录即可（**脚本按文件名关键字识别包**：含 `300` → 2018，含 `2017` → 2017，其余 → 2016）：

```bash
python apk_analysis/inspect_archives.py
python apk_analysis/analyze_static.py
python apk_analysis/inspect_native.py ciyuan_2017 checkFileCompress
python apk_analysis/decode_resources.py
python apk_analysis/inspect_decoded.py
python apk_analysis/inspect_proto_schema.py ciyuan_2017
python apk_analysis/write_report.py
```

`analyze_static.py` 是全量扫描（3.2 GB 数据），耗时较长；其余脚本在数分钟内完成。

---

## 一个容易踩的坑：必须在解密后比对

对**加密字节**做比对会得出"三包毫无重叠"的错误结论（早期 `comparison.json` 中 `identical_assets` 全为 0）。原因是每个文件的 deflate 输出不同，且头部含长度字段。

对**还原后内容**比对（`decoded_comparison.json`，SHA-256）才是真实结论：

| 对比 | 同路径资源 | 内容完全相同 |
|---|---:|---:|
| 次元大作战 ↔ 魔霸之王 | 2,427 | **1,704** |
| 次元大作战 ↔ 300大作战 | 623 | 117 |
| 300大作战 ↔ 魔霸之王 | 342 | 82 |

2016↔2017 一致的 1,704 个资源中包含 426 个 `.x2` 模型、705 个 `.pkm` 贴图、225 个 `.ccz`、259 个 `.ini` 特效配置、10 个 Lua。结合相同的 `Tombird` 入口与相同的封装算法，可以支持"共享引擎、客户端代码与资源存在沿袭"的判断；但**不足以**认定完整的商业授权或产品演变史——三包签名证书指纹互不相同，不是同一签名的覆盖升级包。

---

## 资源目录结构

还原后的 `decoded/` **只还原 `assets/`**；`lib/*.so`、`classes.dex`、`res/`、`AndroidManifest.xml` 仍在 `unpacked/` 中。三代骨架一致：

| 目录 | 内容 | 主要格式 |
|---|---|---|
| `assets/config/` | 渠道 / 支付 / SDK 全局配置 | `.lua`（明文） `.png` |
| `assets/data/conf/` | 数值配置表 | `.dat`(protobuf) `.csv` `.proto` `.txt` |
| `assets/data/script/` | 游戏逻辑 | `.lua`（明文） |
| `assets/data/model/` | 模型、特效、动画 | `.pkm` `.x2` `.ini` `.tga` |
| `assets/data/texture/` `ui/` `ui_new/` `ui_hd/` | 贴图与界面 | `.ccz` `.pkm` `.plist` `.png` |
| `assets/data/sound/` | 音频 | `.bank`（FMOD） |
| `assets/data/shader/` | 渲染着色器 | `.vs` `.ps` `.glsl`（纯文本） |
| `assets/data/map/` | 地图 | `.xmap` `.tga` `.bin` |
| `assets/data/font/` | 字体 | `.ttf` |
| `assets/drawable-*` | Android 图标族（仅 2017 包） | `.png` |

三代之间可见的演进：2017 / 2016 的界面贴图用 `.ccz`（zlib 容器，内层通常仍是 `.pvr`，**本次未再解一层**），2018 已全面改为 `.pkm`（ETC1，GPU 直接可用）；2018 额外拆出 `ui_hd/` 高清包与 `hotfix_res/` 热更目录，并带一个内含 6 个 Lua 的 `editor/` 调试入口；Lua 逻辑量从 79 → 165 → 546。

---

## 仓库收录范围

**收录**：全部分析脚本、`*.json` 元数据与证据报告、`分析报告.md`、反汇编片段（`.disasm.txt`）、DEX 类名清单、可读清单 `AndroidManifest.decoded.xml`。

**不收录**（由 [`.gitignore`](.gitignore) 排除，均可由脚本重新生成）：

| 排除项 | 原因 |
|---|---|
| `*.apk` | 版权素材，且合计 800+ MB |
| `apk_analysis/*/unpacked/` | ZIP 全量解包结果，可由 APK 重新生成 |
| `apk_analysis/*/decoded/` | **解密后的游戏素材**，版权内容，可由脚本重新生成 |
| `*/dex_strings.txt`、`*/native_core_strings.txt` | 从二进制批量导出的原始字符串，体积大且无分析价值 |
| `apk_analysis/*_preview.png` | 游戏图标 / 加载画面合成图 |

因此克隆本仓库后**无法直接得到游戏资源**，需要自备原始 APK 并运行流水线。

---

## 专题分析：《次元大作战》2017 战斗核心逻辑

三包中研究重心为 `ciyuan_2017`。战斗系统专题见 **[`apk_analysis/ciyuan_2017/战斗逻辑分析.md`](apk_analysis/ciyuan_2017/战斗逻辑分析.md)**。

结论：**权威服务器状态同步，不是帧同步**。

- 全部 164 个 Lua 文件中 `lockstep` / `predict` / `interpolat` / `rollback` / 逻辑帧号 **0 命中**；`frame` 只出现在 UI 边框和本机时钟 `JScript_GetGameFrameTime()`。
- 服务端按**视野（AOI）**下发进入/离开视野的实体**完整快照**（`OnMsgPlayerEnterMySight`、`CSnapShot*Data`），帧同步不需要视野管理。
- 客户端**本地移动先行 + 服务端校正**：`CRoleMoveCtrl::SendAndMove()` 发出意图的同时自己先走；`onMsgPlayerVerifyPos` 反汇编显示服务端下发的 **int16 定点坐标**被还原为浮点后交给 `CMoveCtrl::PushPlayerVerify` 推入本地移动控制器——帧同步下位置天然一致，无需校验。
- **伤害 100% 在服务端算**：上行只有 `SSkillPreFire`（技能ID/等级/方向/目标），下行是 `SSkillReply`（含每目标 `NHurt`、`NCurHP`、伤害来源明细 `VPackDamageInfo`）。客户端原生库中**没有任何 `CalcDamage`/`CaluHurt` 函数**，只有攻速、移速、移动方向三类计算。
- 技能配置表只有 `NFormulaID` + 伤害系数，**公式本体在服务端**；`SSkillReply.UFormulaBalanceCounts` 是公式的平衡版本号。
  → **更正**：做完整还原尝试后确认，这些字段在客户端 schema 中存在但在随包数据里**出现 0 次**（`NFormulaID`/`NGodFormulaID`/三个 `NDamageCoefficient*` 在 2050 条技能记录中均为 0），因此**连公式的输入参数也不在客户端**。客户端的属性词汇表（24 个属性 ID）与全部属性数值倒是完整的（`hero_c` 35 条、`item_armour_c` 290 条、`skill_skilllevel_c` 2050 条等 41 张表已解码），缺的恰好是**减免曲线**与**技能系数**。

因此：协议与数值配置可完整还原，**权威战斗模拟无法从客户端还原**。客户端连自己的位置都不完全信任，却从不计算自己造成了多少伤害。

### 配置表解码与伤害公式的还原尝试

`decode_config_tables.py` 用恢复出的 schema 解码 `conf/*.c.dat`：**55 张表中 41 张成功解码**（`hero_c`→`SHero`、`item_armour_c`→`SItem_Armour`、`skill_skilllevel_c`→`SSkill_SkillLevel` 2050 条、`monsterdata_c`→`SExcelMonster` 480 条等）。

`analyze_attributes.py` 从 `SGrowUpGenius.SDescription`（"物理攻击+1"）与 `SRuneMapData.Stips`（"物理攻击"）两处中文标签交叉恢复了 **24 个属性 ID**（30=物理攻击、31=魔法强度、42/43=物理护甲、44/141=魔法抗性、95=自身造成的伤害提升、97/98=生命偷取/法术吸血、106~109=护甲/魔法穿透…），并审计了伤害公式字段的填充情况：

| 字段 | schema 字段号 | 在 2050 条技能数据中出现 |
|---|---:|---:|
| `NFormulaID` / `NGodFormulaID` | 20 / 21 | **0** |
| `NDamageCoefficientFirst` / `...Second` / `...S` | 54 / 55 / 81 | **0** |
| `NAttackRate` / `NHitAddons` / `NIfKeepAttack` | 14 / 15 / 32 | **0** |
| `NDamageType` | 82 | 2050 |

序列化器**显式写入零值**（2050 条中 1674 条含值为 0 的 `NCostMP`），所以字段缺失等于数据里真的没有。全局表 `logic_c.dat`（117 条）全是经济/UI 参数、技能描述只有定性文案、`Script_GetSkillDamageInfo` 的五处引用全被注释——**2017 的伤害公式无法从客户端还原**。

**但对另外两个包做同样审计后有了转折**：`game300_2018` 的 3276 条技能记录**全部填充了** `NFormulaID` 与三个伤害系数，而且它的客户端 Lua 里就有公式本体——`bat_skill_desc_ui.lua` 中按公式 ID 索引的 `damageValueStringFunc` 分发表：

```
减免前伤害 = NDamageCoefficientFirstSecond + floor(攻击力 × NDamageCoefficientFirst × 0.01)
```

即 `First` = 物理攻击百分比系数、`FirstS` = 魔法强度百分比系数、`FirstSecond` = 固定基数，公式 ID 决定用物攻/魔攻/两者以及伤害类型（物理/魔法/真实/回复）。2016 与 2017 则完全没有这些字段。详见 **[伤害公式还原](apk_analysis/伤害公式还原.md)**。

仍未找到的是**护甲减免曲线**——三个包的客户端里都只有 UI 文案与属性显示，没有任何减免计算代码。

### 单英雄档案：107 三笠

[`apk_analysis/ciyuan_2017/英雄107_三笠.md`](apk_analysis/ciyuan_2017/英雄107_三笠.md) 是配置侧 + 资源侧的完整档案，可作为单英雄检索的模板：

- **数值**：基础物攻 90、物攻成长 2.8，**两项均为 35 个英雄中的第 1**；无蓝耗、怒气资源条
- **技能**：`NProfession==107` 的 17 个技能（含普攻 2961、被动 2979、爪钩 3101–3103），CD / 蓝耗 / 射程 / 等级数 / 伤害类型齐全
- **皮肤** 1 套（换语音、5 个技能换特效、独立模型 `107_skin1.x2`）
- **天赋** 5 组 15 个；**推荐出装**三组已联查 `item_item_c` + `item_item_lan_c` + `item_armour_c` 解出名称与属性
- **资源** 57 个文件：30 个技能特效、15 个 UI 立绘、模型 `107.x2`/`107.pkm`、FMOD 语音、技能图标
- 顺带发现 `SSkill_SkillLevel.StrUseSkillMsg` 在 2050 条记录中**全部是字面量 `"test"`**（开发期占位符，非有效数据）

[`apk_analysis/ciyuan_2017/英雄107_战斗逻辑.md`](apk_analysis/ciyuan_2017/英雄107_战斗逻辑.md) 是她的战斗机制拆解：气体（怒气）资源链、六个被本地化技能的完整机制、子技能链（`StrLevelUpBindSkill` / `NShowLogSkillIndex`）、逐级伤害与冷却，以及**写在描述文本里的伤害系数**——`{~30*00.50}` 即 `0.5 × 物理攻击`，与 `_Lan` 表的 `(0.5AD)` 互相印证（属性 30 的含义同时被客户端 `gamedef.lua` 的 `Attr_PhysicsAttackMax = 30` 独立确认）。

---

## 专题分析：EMA 发行链与 SDK

[`apk_analysis/emagroup发行链与SDK.md`](apk_analysis/emagroup发行链与SDK.md) 记录了发行方**亿马联盟（EMA）**侧的后端与 SDK 分层。起点是一份公开的 EMA 渠道项目源码（`nick-yangzj/MyMatch1`，Unity/C# 三消练手项目，**不是**目标游戏），它携带了可读的 EMA SDK 包装与配置拉取地址，正好可以给三个 APK 里只能看到字符串的后端做对照。

四条结论：

- **EMA SDK 有两代，且两包各用一代**：2016 是内嵌的 `EmaSDK.java` + `sdk.emagroup.cn/{esdk_api,gather/info,pay,sys}`；2017 换成独立包 `com.emagroup.sdk`（dex 中 `Lcom/emagroup/sdk/` 出现 **251** 次）+ `api.emagroup.cn/ema-platform/*` 的 19 个 REST 端点。2018 则 **EMA 痕迹全部为 0**。
- **`assets/developerInfo.xml`（2016）恢复了平台侧标识**：`ema_app_id="3"`（即《魔霸之王》在 EMA 平台的编号）、`ema_channel_id="2"`、备用域 `esdk2.emagroup.cn`、OAuth 落点 `payment.ddmoba.com/emaredirect.html`。
- **CDN 代号链 = 产品线三代自证**：`kom.cdn.emagroup.cn/Android/`（2016）→ `kom.cdn.emagroup.cn/moba02/Android/`（2017）→ 备用 `download.jumpw.com/ciyuan/Android/`。即 `kom`(魔霸之王) → `moba02`(魔霸之王2/次元大作战) → `ciyuan`(次元)。2017 的 `config.lua` 里内购商品号是 `CYDZZ_1000`~`CYDZZ_1006`。
- **三包共用 Jumpw 账号/支付层**：`300hero.jumpw.com`、`testactivity.jumpwgame.com`、`payment.ddmoba.com/payordercreate.html` 在**三个包的原生库里都有**，且协议中存在 `Sa2gLoginTypeNotJumpw`（"非 Jumpw 登录类型"）消息——账号与支付通道是同一套，比"共享引擎与资源"更进一步。

另外确认了一个**机制性事实**：2017 的 `assets/data/script/tables/serverlist.lua` 只是 CSV 读取器，**包内不含任何服务器 IP**，服务器表由网关在运行期下发（客户端按 `config.lua` 的 `g_nClientServerIndex = 3` 筛选）。所以"从客户端恢复出目标服务器列表"在方法上不可行，而不是我们没找到。

该源码作者的其余仓库也已全部核查（[作者仓库与框架脉络](apk_analysis/nick-yangzj仓库清单分析.md)）：**没有任何 EMA 服务端代码**，其中 4 个框架仓库均为未改动的 fork（含一处对本文档初版"框架作者"表述的更正）。核查过程另有一个收获——从恢复出的 protobuf schema 里读出了**目标包自己的服务端拓扑**：网络消息遵循 `S<源>2<目标><Req|Ack><动作>` 命名，出现 `c`(客户端) / `g`(游戏服) / `a`(账号发货服) 三种角色，登录必须由 `g` 中转（`c→g` `Sc2gReqClientLogin`、`g→a` `Sg2aReqClientLogin`、`a→g` `Sa2gAckClientLogin`、`g→c` `Sg2cAckClientLogin`+`Sg2cSecretKey`）。

---

## 已知限制

- `decode_resources.py` 的密钥寻址**硬编码于这三个确切文件的地址**（`ciyuan_2017` 的 `libgame.so`），换版本或换包会失效；但同一密钥已验证对另外两包同样有效。
- 2016 / 2017 包没有 `.proto`——此问题已由 `inspect_proto_schema.py` 从客户端 `k*FieldNumber` 常量恢复字段号解决；但**只恢复了字段号，字段类型尚未恢复**。
- `.ccz` 内层的 `.pvr`、`.x2` 模型、`.bank` 音频、`.xmap` 地图**仍是私有 / 未转换格式**，本次没有、也不会把它们伪称为已转换的通用格式。
- 核心 C++ 逻辑仍是机器码，**未还原为可编译工程**；`libgame.so` 只反汇编了关键函数。
- 全部工作为**离线静态分析**：没有运行游戏，没有安装到设备，**没有连接包内任何登录 / 支付 / 更新服务器**。报告中出现的域名与 IP 仅作为字符串证据记录，不代表其当前可用。

---

## 免责声明

- 三款游戏均为**已停运的商业产品**，其代码、美术、音频、文案等全部权利归各自权利人所有。本仓库作者与任何权利人**无关联、无授权关系**。
- 本仓库仅出于**个人学习与文件格式研究**目的，记录分析方法与结论，**不提供、不再分发任何游戏素材或原始二进制**。
- 请勿将本项目及其衍生内容用于**私服运营、破解分发、商业用途**或任何侵犯他人权利的场景。
- 若权利人认为本仓库内容不当，请通过 issue 联系，将立即删除相关内容。

---

## 详细报告

完整的中文分析报告（含权限清单、SDK 集成、联网字符串、签名证书、SHA-256 原始指纹等章节）见 **[`apk_analysis/分析报告.md`](apk_analysis/分析报告.md)**。

原始 APK 的 SHA-256：

| 文件 | SHA-256 |
|---|---|
| `魔霸之王【2016年4月1日】.apk` | `b447947befd9fdb9569af2b3626e3cee2947d25e76add4b5b5e82fab5e37dfda` |
| `次元大作战【2017年6月】.apk` | `57ac48171d3b15e41607f956b762c2a76b24fdb2b0027476b741bcd43ce5ddbf` |
| `纯300大作战【2018年10月6日】.apk` | `15a01c3476f6e1c7b8d038f65bfab459fe1bd466cf38b0606518f11fbb3ecddc` |
