from pathlib import Path
import json,collections

ROOT=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
slugs=['moba_2016','ciyuan_2017','game300_2018']
data={s:read(ROOT/s/'summary.json') for s in slugs}
dec={s:read(ROOT/s/'decoded_inventory.json') for s in slugs}
findings={s:read(ROOT/s/'decoded_findings.json') for s in slugs}
def link(slug,path,label):return f'[{label}]({(ROOT/slug/path).as_posix()})'
lines=[
'**三个 APK 的静态解包与内容分析**',
'',
'检查日期：2026-09-23（以任务日期为准）。原始 APK 保留。分析包括 ZIP 全量提取及 CRC 校验、SHA-256、Android 二进制清单与资源表解析、DEX 类名和字符串、签名证书读取、ARM 库静态反汇编、游戏资源封装恢复和资源哈希对比。未安装或运行游戏，未连接包内的登录、支付、更新等服务器。',
'',
'最主要的发现是：三者共享明显的技术基础；《魔霸之王》和《次元大作战》的联系尤其直接。资源封装已全部恢复，可以直接阅读 Lua、CSV、INI、着色器及部分 Protobuf 定义，并继续处理模型、纹理和音频。',
'',
'| 文件对应游戏 | 清单版本 / versionCode | 包名 | APK 大小 | ZIP 文件数 | Lua 文件数 | hero_c.dat 记录数 |',
'|---|---|---|---:|---:|---:|---:|'
]
for s in slugs:
 a=data[s];f=findings[s]
 lines.append(f"| {a['app_labels'][0]['value']}（{s[-4:]}） | {a['manifest']['android:versionName']} / {a['manifest']['android:versionCode']} | `{a['manifest']['package']}` | {a['size']/2**20:.1f} MiB | {a['file_count']:,} | {f['lua_files']} | {f['hero_records']} |")
lines += [
'',
'年份来自原文件名，不是对发行日期的独立认证。英雄记录数是包内这张表的条目数，不等于当年正式开放或实际可用的英雄总数。Lua 数量包括启动配置、界面及工具脚本。',
'',
'**技术与内容**',
'',
'- 三包的原生库都包含 Cocos2d-x、Lua 5.1、LuaJIT 2.0.1 标记，均有 FMOD 音频库。核心分别为 `libtombird.so`（2016）和 `libgame.so`（2017、2018）。',
'- 2016、2017 仅包含 `armeabi` 原生库；2018 仅包含 `armeabi-v7a`。这些均为 32 位 ARM ELF，未发现 ARM64 或 x86 原生库。',
'- 游戏资源集中在 `assets/data/`：`conf` 为英雄、技能、装备、皮肤、活动等配置，`script` 为 Lua，`model` 为模型与特效，`map` 为地图，`shader` 为着色器，`sound/mobile` 为音频，`ui` / `ui_new` 为界面资源。',
'- 常见格式包括 `.x2` 模型、`.xmap` 地图、`.pkm` / `.pvr.ccz` 纹理和 FMOD `.bank` 音频。去除外层封装后，这些格式仍需对应查看器；没有把它们伪称为已转换的通用模型或 WAV。',
'- Lua 中可看到登录、资源热更新、服务器列表、大厅、选人、战斗界面、背包、商城、充值、公会等客户端模块。核心 C++ 代码仍是机器码，本次未还原成完整 C++ 工程。',
'',
'**三个包各自的特征**',
'',
'1. 《魔霸之王》1.20：包名带 `.baidu`，Application 是 `com.baidu.gamesdk.BDGameApplication`，签名证书主体含百度公司，`BDPChannelID.xml` 内渠道号为 `5004211`。可确认带百度/多酷渠道集成；同时包含支付、个推和统计相关 SDK。',
'2. 《次元大作战》2.16：包名为 `com.emagroup.mbzw2.emagroup`，主入口仍是 `cn.emagroup.kom.Tombird`，与 2016 包一致。集成 Emagroup、AnySDK、个推、支付宝、腾讯/微博、DataEye 等类与组件。英雄表中可见 `Name_Saber`、`Name_tongren`、`Name_chuyinweilai`、`Name_yubanmeiqin` 等名称键；本地字符串表可直接读到黑岩射手、夏娜、三笠、桐人、御坂美琴等文字。名称键、遗留文案与实际可玩内容需区分。',
'3. 《300大作战》1.33：包名为 `com.jumpw.mobile300`，主入口改为 `com.jumpw.mobile300.Tombird`，Application 为 Jumpw SDK。包含友盟、Bugly、讯飞和游密语音相关代码/库。配置启用 `_jp` 配音前缀和 `japan_` 看板娘前缀，这只能说明资源选择，不足以证明它是日本发行版。',
'',
'2018 包还带有 50 个 `.proto` 文件，能够看到英雄属性、技能、商店、任务等数据结构；`data/editor/script` 有 6 个场景/角色/文件操作相关编辑器脚本。`gametest.txt` 与 `subroot/gametest.txt` 是短测试文本，不应仅凭 `subroot` 名称判断为提权功能。',
'',
'**资源封装恢复结果**',
'',
'大多数游戏资源原本以 `MP:` 开头，而不是扩展名对应的标准文件头。从原生 `CCFileUtils::checkFileCompress` 函数确认其处理方式：12 字节头、循环 XOR、zlib 解压；头中记录解压长度。同一读取参数成功恢复了三包全部 MP 资源。每个输出均检查 zlib 流完整性、校验和和解压长度；失败数为 0。',
'',
'| 游戏 | 成功恢复的 MP 文件 | decoded 中全部资源文件 | decoded 资源大小 |',
'|---|---:|---:|---:|'
]
for s in slugs:
 d=dec[s];lines.append(f"| {data[s]['app_labels'][0]['value']} | {d['decoded_mp_files']:,} | {d['resource_count']:,} | {d['decoded_bytes']/2**20:.1f} MiB |")
lines += [
'',
'`decoded/assets/` 同时包含恢复后的资源和原本未封装的资源。790 个 Lua 文件恢复后为文本形式；Protobuf `.dat` 文件恢复后仍为二进制数据，本次另导出了英雄 ID / 名称键。2017、2018 字符串表按 GB18030 解码导出；名称键无法精确匹配的条目标记为 null，没有凭猜测补齐。',
'',
'**三者关联的实证**',
'',
'| 对比 | 同路径资源数 | 恢复后内容完全相同的资源数 |',
'|---|---:|---:|'
]
for c in read(ROOT/'decoded_comparison.json'):
 lines.append(f"| {data[c['a']]['app_labels'][0]['value']} ↔ {data[c['b']]['app_labels'][0]['value']} | {c['common_paths']:,} | {c['identical_decoded_assets']:,} |")
lines += [
'',
'相同文件通过恢复后内容的 SHA-256 比对确认。2016↔2017 的 1,704 个一致资源包括 426 个 `.x2`、705 个 `.pkm`、225 个 `.ccz`、259 个 `.ini`、10 个 Lua 等。2017↔2018 的 117 个一致资源包括 12 个 Lua、11 个 `.x2`、16 个 `.dat` 及多种着色器。',
'',
'结合相同 Tombird 入口、相同封装算法和读取参数、大量相同游戏资源，可以支持“共享引擎与存在客户端代码/资源沿袭”的判断；仅凭这些不能认定完整产品演变史、商业授权关系或全部逻辑相同。三个签名证书指纹不同，也不能把它们视为同签名覆盖安装升级包。',
'',
'**联网、权限与分析边界**',
'',
'| 游戏 | assets/version.json 的更新地址 | 包内更新版本字段 |',
'|---|---|---|'
]
for s in slugs:
 v=findings[s]['versions']['assets/version.json'];lines.append(f"| {data[s]['app_labels'][0]['value']} | `{v['Url']}` | App={v['App']}, Res={v['Res']} |")
lines += [
'',
'`version.json` 中的 App/Res 是游戏自己的更新字段，不等同于 Android 清单的 versionCode。2017 包另有 `version_copy.json` 指向 `download.jumpw.com/ciyuan/Android/`，App/Res 均为 999；这里只记录文件存在，不假定运行时采用该备用文件。',
'',
'恢复后的 2018 `script/tables/serverlist.lua` 使用 `http://api.jumpw.com/GetGameConfig.html` 构建服务器列表请求，保留测试配置及注释中的服务器示例；这不表示那些地址目前仍可用。三包都能发现 `payment.ddmoba.com` 或相关支付/活动字符串，2017 配置使用 `payment2.ddmoba.com`。部分地址是示例、测试、注释或第三方 SDK 内容，字符串存在不等于运行时一定访问。',
'',
'- 2016 包声明读/收/发短信、电话、相机、定位、悬浮窗、设备状态和外部存储等权限；权限范围较广。',
'- 2017 包声明定位、设备状态、账户、悬浮窗、开机接收等权限。',
'- 2018 包声明录音、发送短信、定位、设备状态、外部存储和悬浮窗等权限；录音相关库与语音功能相符。',
'- 声明权限不代表系统实际授予；部分系统级/过时权限普通应用无法取得。SDK 存在及权限声明不足以判断恶意行为。',
'- 不少历史接口使用 HTTP。清单 targetSdk 分别为 18、22、19；兼容性和真实运行情况需要另行在合适环境测试。',
'- 签名证书已读取，但本次没有完成 APK 签名验签、官方发行源比对或动态安全检测；ZIP CRC 通过仅表示归档条目读取校验通过，不是官方性或安全保证。',
'- APK 中有客户端与联网/热更新逻辑，没有恢复出可直接运行的服务端工程，不能据此声称已经能离线开服或进入对战。',
'',
'**结果位置**',
'',
'每个游戏子目录中：`unpacked/` 是原始 ZIP 解包结果；`decoded/assets/` 是外层封装恢复后的资源；`AndroidManifest.decoded.xml` 为可读清单；`summary.json` 为元信息；`inventory.json` 和 `decoded_inventory.json` 为完整文件、大小和哈希；`heroes.json` 为英雄表摘要；`network_strings.json` / `decoded_network_references.json` 为联网字符串及来源。',
''
]
for s in slugs:
 lines.append('- '+data[s]['app_labels'][0]['value']+'：'+link(s,'decoded/assets','恢复后的资源')+' · '+link(s,'AndroidManifest.decoded.xml','应用清单')+' · '+link(s,'heroes.json','英雄记录'))
lines += ['',f"[三款应用图标]({(ROOT/'icons_preview.png').as_posix()}) · [300 大作战加载画面]({(ROOT/'game300_loading_preview.png').as_posix()})",'',
'可复查脚本：`inspect_archives.py`、`analyze_static.py`、`inspect_native.py`、`decode_resources.py`、`inspect_decoded.py`。解码脚本中的库地址针对本次这三个确切文件，不保证适用于其他版本。',
'',
'**原始文件 SHA-256**','']
for s in slugs:
 a=data[s];lines += [f"- `{a['source']}`：`{a['sha256']}`"]
(ROOT/'分析报告.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('report',ROOT/'分析报告.md')
print('total_decoded_mp_files',sum(x['decoded_mp_files'] for x in dec.values()))
print('total_lua_files',sum(x['lua_files'] for x in findings.values()))
print('all_errors',sum(len(x['errors']) for x in dec.values()))
