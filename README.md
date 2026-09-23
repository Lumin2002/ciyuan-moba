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

年份取自原始 APK 文件名，不是对发行日期的独立考证。三包同为 Cocos2d-x + Lua 5.1 / LuaJIT 2.0.1 + FMOD 架构，主入口类都是 `Tombird`，核心原生库为 `libtombird.so`（2016）与 `libgame.so`（2017 / 2018）。

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
| 6 | `inspect_proto_schema.py` | 从原生库的 `k*FieldNumber` 常量恢复 protobuf schema（字段号），并与 2018 的 `.proto` 交叉验证 | `proto_schema_recovered.json`、`proto_schema_crosscheck.json` |
| 7 | `write_report.py` | 汇总上述 JSON 生成完整中文报告 | [`apk_analysis/分析报告.md`](apk_analysis/分析报告.md) |

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

因此：协议与数值配置可完整还原，**权威战斗模拟无法从客户端还原**。客户端连自己的位置都不完全信任，却从不计算自己造成了多少伤害。

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
