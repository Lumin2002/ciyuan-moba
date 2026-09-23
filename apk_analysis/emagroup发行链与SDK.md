# 亿马联盟（EMA）发行链与 SDK

> 起因：在检索三个目标包的外部资料时找到了 [`Avatarchik/MyMatch1`](https://github.com/Avatarchik/MyMatch1)（`nick-yangzj/MyMatch1` 的 fork）。它本身**不是**三款目标游戏，但它是**唯一一份能读到的 EMA 发行链一手代码**：里面既有 EMA Android SDK 的客户端封装，也有指向 `cdn.emagroup.cn` 的配置拉取地址。
>
> 本文把「MyMatch1 是什么」与「它给本次逆向补上了什么」分开写清楚，并把从它和三个 APK 里恢复出来的 EMA 后端域名整理成表。**所有结论都标注了证据来源。**

---

## 0. 一句话结论

| 问题 | 结论 |
|---|---|
| MyMatch1 是三款目标游戏之一吗？ | **不是**。Unity 5.3.4f1 + C# + ToLua 的三消项目，引擎与目标包（Snake + cocos2d-x + C++/Lua）完全不同 |
| 那它为什么和本项目相关？ | 它是 **EMA 发行链的样本**：带 EMA Android SDK 的 Unity 侧包装，运行时从 `cdn.emagroup.cn` 拉配置 |
| 它有目标包的代码吗？ | **没有**。两侧 SDK 是**同族不同代**，方法名有交集但包装类无交集（见 §3） |
| 它最直接的价值 | 把三个 APK 里只能看到字符串的 EMA 后端，变成**可读源码 + 可读配置**，并解释了 SDK 的两代演进 |

---

## 1. MyMatch1 身份鉴定

**证据**：GitHub API（`/repos`、`/git/trees/master?recursive=1`、`/contents`）与 `raw.githubusercontent.com` 原文。

| 项 | 值 |
|---|---|
| 仓库 | `Avatarchik/MyMatch1`（fork）/ 上游 `nick-yangzj/MyMatch1` |
| 语言 / 体积 | C# / 153,456 KB；默认分支 `master`；README 全文只有一行 `# MyMatch1` |
| 引擎 | **Unity 5.3.4f1**（`ProjectSettings/ProjectSettings.asset` 内版本串） |
| productName | **我的三消** |
| bundleIdentifier | `com.nickyangzj.sanxiao` |
| companyName | `Mius` |
| 版本 | `1.0`（bundleVersion / AndroidBundleVersionCode = 1） |
| 构建场景 | `StopAudio;FightTest1;APPSTORE1` |
| 第三方 | NGUI **3.9.7**、JMO Assets / Cartoon FX、BestHTTP、ToLua（tolua#） |
| 脚本骨架 | `Assets/_Scripts/FrameWork/`（ToLua、UIManager、**NetWorkManager**、Http、Timer、LuaManager、ResManager…）+ `Assets/_Scripts/GameLogic/`（Fight、FightNew、UI、**Sdk/EmaAndroidSDK**） |
| Lua | ToLua 明文 Lua 在 `Assets/_Scripts/FrameWork/ToLua/Lua/`（cjson、protobuf、socket、math、system） |
| 玩法 | 三消 PvP：`Fight/Card/{CrossBomb,SimpleChip,StoneChip,UltraColorBomb}.cs`、`Slot*`、`Block/*`、`Boss`、`Dragon`，外围 `Arena`/`Matching`/`RankChange`/`WinLose` |

> **更正**：本文件初版曾写「`nick-yangzj` 是 Scut 与 ET 的作者」，**这是错的**。GitHub API 显示 `nick-yangzj/Scut` 与 `nick-yangzj/ET` 均为 `fork=true`，分别 fork 自 [`ScutGame/Scut`](https://github.com/ScutGame/Scut)（1,340 star）与 [`egametang/ET`](https://github.com/egametang/ET)（9,916 star），且两个 fork 的 `pushed_at` 与父仓库当时的 HEAD 完全一致——**他从未提交自有改动，只是留了参考镜像**。详见 [作者仓库与框架脉络](nick-yangzj仓库清单分析.md)。

顺带说明：他的仓库清单里**没有任何 EMA 游戏服务端代码**，MyMatch1 是本账号唯一与 EMA 相关的产物。

> 因此 MyMatch1 是**个人练手项目**（`com.nickyangzj.sanxiao`、companyName 为个人名号 `Mius`、README 一行），而不是某个商业产品。但它被作者**按 EMA 渠道的实际形态**配置过——见 §2 的 `#if NEWEMA` 分支。

---

## 2. 它携带的两样东西

### 2.1 EMA Android SDK 的 Unity 侧包装

`Assets/_Scripts/GameLogic/Sdk/EmaAndroidSDK/` 四个文件：

| 文件 | 作用 |
|---|---|
| `SDKEMAController.cs` | 单例 `MonoBehaviour`，SDK 生命周期入口与回调分发 |
| `SdkBase.cs` | 抽象基类，8 个空虚方法 |
| `SdkForAndroid.cs` | Android 实现，`#if NEWEMA` 分支内用 `AndroidJavaClass` 调 Java 静态方法 |
| `SdkLogin.cs` | 登录界面：初始化 → 登录 → 连游戏服务器 |

`SdkBase` 定义的 API 面（**这正好就是 EMA 原生 SDK 的方法集**）：

```csharp
public virtual void Init(int flag = 0){}   public virtual void Login(){}
public virtual void Logout(){}             public virtual void Pay(string payInfo){}
public virtual void GameCenter(){}         public virtual void ResetPayState(){}
public virtual void GameInfo(string gameInfo){}   public virtual void DoQuitSdk(){}
```

`SdkForAndroid` 的 `#if NEWEMA` 分支：

```csharp
jc = new AndroidJavaClass("com.mius.sdmb.sdk.SdkApi");
jc.CallStatic("Init", flag);   // Login / Logout / GameCenter / Pay / ResetPay / GameInfo / DoQuitSdk 同理
```

> **注意**：包名是 `com.mius.sdmb.sdk.SdkApi`——`mius` 是作者的 `Mius`，`sdmb` 未解析（见 §11）。**这个字符串在三个目标包的 dex 里都不存在。**

`SDKEMAController` 的回调协议（对写外部工具最有用）：

```csharp
public enum EnumCallMsg {
    InitSuccess=0, InitFail=1, LoginSuccess=2, LoginFail=3, LoginCancel=4,
    LogoutSuccess=5, LogoutFail=6, PaySuccess=7, PayFailed=8, PayCancel=9,
    PayOrderSubmitted=10, PayArgsError=11, LoginSwitch=12,
    GameContinue=13, GameExit=14,
}
public void OnResponseClient(string msg)   // msg 是十进制数字串，Convert.ToInt32 后 switch
```

渠道号换算与一个渠道特判：

```csharp
public static int ReceivedChanelId = 199;
public void ReceiveChanelId(string chanelId) {   // 解析失败则回落到 199
    ReceivedChanelId = int.TryParse(chanelId, out var p) ? 100 + p : 199;
}
public static bool IsTBT { get { return SDKEMAController.ReceivedChanelId == 207; } }  // 207-100=107
```

支付与用户信息回传：

```csharp
public void ReceiveOrderId(string orderId)   // GetOrderId(1/2) 回报订单结果
public void ReceiveUserId(string userId)
public void ReceiveQuitInfo(string quitInfo) // "ExitByGame" → 弹"确定要退出游戏?"
public void SendGameInfo(int lv, string userId, string userName)  // roleId/roleName/roleLevel/zoneId/zoneName/dataType/ext
```

登录成功后的串联（`SdkLogin.cs`）：`NetworkManager.Instance.SendReConnect()` → 收到 `OnConnectSocket` 事件后再 `Util.CallMethod("UILoginCtrl","SendLogin", UserId, ChannelId, "")`。**即「SDK 登录 → 连 socket → 用 SDK 返回的 userId 换游戏会话」**，这正是三个目标包里 `Tombird` + `DoPayCallBack` 那条链路的同族形态。

### 2.2 服务器清单与配置拉取地址

`Assets/_VerInfo/VerInfo.txt`（本地回退副本，**原文**）：

```json
{"list":[{"SocketIp":"116.228.88.149","Port":5555,"Ver":"1.0"},
         {"SocketIp":"192.168.10.28","Port":5555,"Ver":"1.1"},
         {"SocketIp":"games.emagroup.cn","Port":5555,"Ver":"99"}],
 "otherData":1000}
```

- `Ver 1.0` → 上海电信 IP `116.228.88.149`
- `Ver 1.1` → `192.168.10.28`，**办公局域网地址**（`.10.28` 是 EMA 内网段）
- `Ver 99` → **`games.emagroup.cn:5555`**，生产网关
- `otherData: 1000` 用途未确认

`Assets/_Scripts/FrameWork/Http/MyHttp.cs`（**原文节选**）说明这份文件是远程下发的：

```csharp
#if NEWEMA
string url = "http://cdn.emagroup.cn/mymatch/android/VerInfo.txt";
#elif APPSTORE
string url = "http://cdn.emagroup.cn/mymatch/android/VerInfo.txt";
#else
string url = "file://" + Application.dataPath + "/_VerInfo/Verinfo.txt";
#endif
```

**`cdn.emagroup.cn/mymatch/android/`** —— 「我的三消」在 EMA CDN 上有独立目录。也就是说：这个个人项目**确实按 EMA 渠道发布形态配置过**，`Assets/_VerInfo/VerInfo.txt` 只是开发期本地兜底；`NEWEMA` 宏打开时走 EMA 线上配置。

> `games.emagroup.cn`（socket 网关）**在三个目标包中均不存在**——它是另一套（更新/不同）部署的网关，不能当作目标包的服务器地址。

---

## 3. 与三个目标包的交叉验证：同族、不同代

**方法**：把 MyMatch1 的类名/方法名/常量名，与三个包 `dex_strings.txt`（`analyze_static.py` 从 `classes.dex` 批量导出的字符串）逐个比对。

**重要前提**：`dex_strings.txt` 只覆盖 `classes.dex`。目标包的**游戏侧是 C++/Lua**（JNI 出入口为 `cn.emagroup.kom.Tombird`），所以下面的命中与未命中，反映的是 **EMA 原生 Java SDK 的 API 面**，而不是某个 C# 包装类。

### 3.1 命中（API 面同族）

| 符号 | moba_2016 | ciyuan_2017 | 说明 |
|---|---:|---:|---|
| `ResetPay` | 1 | 2 | `SdkBase.ResetPayState` 对应的方法名 |
| `GameInfo` | — | 7 | `SdkBase.GameInfo` |
| `GameContinue` | 1 | — | `EnumCallMsg.GameContinue = 13` |
| `GameExit` | 1 | — | `EnumCallMsg.GameExit = 14` |
| `DoQuitSdk` | 1 | — | `SdkBase.DoQuitSdk` |
| `EmaSDK` / `EmaSDK.java` | 50 / 1 | 15 / 1 | EMA 原生 SDK 主体类 |

### 3.2 未命中（包装层不同代）

以下 MyMatch1 特有符号在三个包中**全部 0 命中**：

`SDKEMAController`、`OnResponseClient`、`ReceiveChanelId`、`ReceiveOrderId`、`ReceiveUserId`、`ReceiveQuitInfo`、`IsTBT`、`mius`、`sdmb`

**结论**：MyMatch1 用的是**第三代包装**（`com.mius.sdmb.sdk.SdkApi`，宏 `NEWEMA`），与 2016/2017 包内嵌的那两代（§4）不是同一份实现，但暴露的**方法名与回调码基本一致**——说明 EMA SDK 的对外契约在几代之间保持稳定。这对「按 API 名反推目标包的 Java 侧调用」是有用的旁证。

> 附带更正一个容易误读的点：2016 与 2017 的 dex 里各有 **1 次** `Lcom/unity3d/player/UnityPlayer;`。两包都是 cocos2d-x/Snake 游戏，这是第三方 SDK 的字符串引用，**不能**据此认为目标包是 Unity 项目。

---

## 4. EMA SDK 的两代：从 `esdk_api` 到 `ema-platform`

这是本次最有信息量的发现——**两个目标包用的是两代完全不同的 EMA SDK，连后端 API 风格都换了。**

### 4.1 2016：老 SDK，内嵌 + `sdk.emagroup.cn`

**证据**：`moba_2016/network_strings.json`、`moba_2016/dex_strings.txt`、`assets/developerInfo.xml`。

后端端点（全部来自 `classes.dex`）：

```
http://sdk.emagroup.cn/esdk_api/activation_code      ← 激活码
http://sdk.emagroup.cn/esdk_api/check_activation
http://sdk.emagroup.cn/esdk_api/take_code
http://sdk.emagroup.cn/gather/info/jh_init           ← 数据采集
http://sdk.emagroup.cn/gather/info/jh_login
http://sdk.emagroup.cn/gather/info/jh_online
http://sdk.emagroup.cn/gather/info/jh_pay
http://sdk.emagroup.cn/sys/version
http://sdk.emagroup.cn/pay/getorderid                ← 来自 assets/developerInfo.xml
http://sdk.emagroup.cn/pay/notice/baidugame
```

DEX 中的类/常量（节选，说明这一代 SDK 是**直接编译进 APK** 的）：

| 字符串 | 含义 |
|---|---|
| `EmaSDK.java`、`EmaActivateView.java`、`EmaBeanOrderInfo.java`、`EmaBeanUserInfo.java`、`EmaOnLineService.java` | SDK 源码文件名（调试信息未剥离） |
| `EmaLogin` / `EmaLogout` / `EmaDoQuit` | 登录/登出/退出入口 |
| `DEVELOPER_CONFIG_EMA_APP_ID` / `..._APP_KEY` / `..._CHANEL_ID` | 从 `developerInfo.xml` 读配置 |
| `ema_sign_key` | 请求签名密钥字段名 |
| `EMA_GATHER_INFO_INIT` / `_LOGIN` / `_PAY`、`EMA_GATHER_ONLINE_TIME`、`EMA_GET_GAME_VERSION_INFO` | 埋点/采集事件名 |
| `cn.emagroup.kom` / `Lcn/emagroup/kom/Tombird` | 本包自己的命名空间；`Tombird` 即 JNI 入口类 |

`assets/developerInfo.xml` **全文**（这是本次恢复出的最有价值的配置；`ema_app_key` 与 `privateKey` 同值）：

```xml
<?xml version='1.0' encoding='UTF-8'?>
<developer><channel BDDebugMode="false" BDPlatformType="0"
  BaiduDKGameAppId="6705975" BaiduDKGameAppKey="9oBkz02K0s0jDxPUGN0lhbB1"
  BaiduGameAppId="6705975" BaiduGameAppKey="9oBkz02K0s0jDxPUGN0lhbB1"
  BaiduGameOrientation="landscape" ExchangeRate="1"
  IAPOnlineBDYouxi_notify_url="http://sdk.emagroup.cn/pay/notice/baidugame"
  OrderURL="http://sdk.emagroup.cn/pay/getorderid"
  callback="http://sdk.emagroup.cn/pay/notice/baidugame"
  ema_app_id="3" ema_app_key="96fe75537ee0f8e92237d36a4474d8b7"
  ema_channel_id="2" extChannel="" idChannel="404"
  oauthLoginServer="http://payment.ddmoba.com/emaredirect.html"
  privateKey="96fe75537ee0f8e92237d36a4474d8b7"
  standby_domain_name="esdk2.emagroup.cn" /></developer>
```

可读出：**`ema_app_id=3` 就是《魔霸之王》在 EMA 平台的编号**；`ema_channel_id=2`；`idChannel=404`；备用域 **`esdk2.emagroup.cn`**；OAuth 重定向落在 **`payment.ddmoba.com`**——`ddmoba` 是 EMA 的支付/活动域（2017 也用它，见 §5）。

### 4.2 2017：新 SDK，独立包 `com.emagroup.sdk` + `/ema-platform/*`

**证据**：`ciyuan_2017/dex_strings.txt`（`Lcom/emagroup/sdk/` **251** 处引用）。

换成了一套 REST 风格的接口族（节选，共 19 个）：

```
/ema-platform/member/checkLogin          /ema-platform/member/getUserInfo
/ema-platform/member/pfLogin             /ema-platform/member/qqLogin
/ema-platform/member/newheartbeat        /ema-platform/member/uploadGameInfo
/ema-platform/order/createOrder          /ema-platform/order/createQQOrder
/ema-platform/order/createWXOrder        /ema-platform/order/confirmOrder
/ema-platform/order/confirmOrderSilient  /ema-platform/order/rejectOrder
/ema-platform/order/queryOrderStatusByOrderId
/ema-platform/billing/setChargePwd       /ema-platform/sign/add
/ema-platform/notice/sendCaptcha         /ema-platform/notice/sendEmailCaptcha
/ema-platform/alipay/notifycallback      /ema-platform/admin/channelKeyInfo
/ema-platform/admin/getSystemInfoEx
```

主机（`classes.dex`）：`http://api.emagroup.cn`、`http://dev.api.emagroup.cn`、`http://test.api.emagroup.cn`——即 **`api` + 三套环境**。

类名（节选，可看出这一代已是完整商业 SDK）：

| 类别 | 类 |
|---|---|
| 主控 | `Ema`、`EmaSDK`、`EmaConst`、`EmaCallBackConst`、`ConfigManager` |
| 登录 | `EmaAutoLogin`、`EmaBinderAlertDialog`、`EmaAlertDialog` |
| 支付 | `EmaPay`、`EmaPayInfo`、`EmaPayInfoBean`、`EmaPriceBean`、`EmaPayListener`、`EmaPayProcessManager` |
| 支付 UI | `EmaDialogPay0YuanFuPassw`、`EmaDialogPay0YuanFuSetPassw`、`EmaDialogSetPayPassw`、`EmaDialogPayPromptCancel`、`EmaDialogPayPromptResult`、`EmaDialogSystemBusy` |
| 运维 | `CrashHandler`、`DeviceInfoManager`、`EmaAnalytics`、`ActivityManager`、`EmaReceiver`、`ToolBar$ToolbarState`、`Base64` |

开关在 Lua 里（见 §5）：`g_nSDKNew = 1`、`recharge_ui.lua:109` 用 `if g_nSDKNew == 1 then` 分流充值流程。

### 4.3 2018：EMA 完全消失

`game300_2018` 的 dex 中 `Lcom/emagroup/sdk/`、`Lcn/emagroup/kom/`、`EmaSDK` **全部 0 命中**。这与「2018 是 Jumpw 自己的产品」一致，也是三包中唯一没有 EMA SDK 的一代。

### 4.4 三代演进对照

| | 2016 魔霸之王 | 2017 次元大作战 | MyMatch1（我的三消） | 2018 300大作战 |
|---|---|---|---|---|
| SDK 形态 | 内嵌 `EmaSDK.java` 等 | 独立包 `com.emagroup.sdk` | Unity C# 包装 + `com.mius.sdmb.sdk.SdkApi` | 无 |
| 后端风格 | `/esdk_api/`、`/gather/info/`、`/pay/`、`/sys/` | `/ema-platform/*` REST | `cdn.emagroup.cn` 配置 + socket 网关 | — |
| 主机 | `sdk.emagroup.cn`、`esdk2`(备用) | `api.emagroup.cn`(+dev/test) | `cdn.emagroup.cn`、`games.emagroup.cn` | — |
| Lua 开关 | — | `g_nSDKNew=1`、`g_nLoginType=eLoginType_Ema` | `NEWEMA` 宏 / `APPSTORE` 宏 | — |

---

## 5. 登录 / 渠道开关（2017 `assets/config/config.lua` 全文）

```lua
eLoginType_Spark = 0
eLoginType_Ema   = 1

g_nLoginType = eLoginType_Ema     -- 登录渠道：Spark 或 Ema
g_bForceServerList = 0
g_NeedTutorial = 1
g_nSDKNew = 1                     -- 使用新版 EMA SDK

-- g_auUrl = "http://120.92.63.244/othersactivitymanager.html" --test
g_auUrl = "http://payment2.ddmoba.com/othersactivitymanager.html" --pro

g_nClientServerIndex = 3
g_uAckPingInterval = 15000

ProductID_IAP_0 = "CYDZZ_1000"  ...  ProductID_IAP_6 = "CYDZZ_1006"
```

要点：

- **`CYDZZ_1000`~`CYDZZ_1006`** = 「**次元大作战**」拼音首字母，是 7 档内购商品号——这是包内自证产品名的又一处证据。
- 活动地址有两套：线上 `payment2.ddmoba.com`，测试 `120.92.63.244`（阿里云杭州）。另外 `activity_ui.lua:1302` 里还硬编码了一个 **`http://payment.kingofmoba.com/othersactivitymanager.html`**——同一个活动管理器同时挂在 **`ddmoba.com`、`kingofmoba.com`、裸 IP** 三个域上。
- 登录类型只有两种：`Spark`(0) 与 `Ema`(1)；`gamecover.lua` 中 3 处按 `g_nLoginType ~= eLoginType_Spark` 分流，并通过 `C_ThirdPartyLogin(g_nLoginType)` 进入第三方登录（`gamecover.lua:809`、`:843`）。
- `g_uAckPingInterval = 15000`（15 s 心跳）与客户端本地移动校验节奏一致。

---

## 6. 服务器表机制

`assets/data/script/tables/serverlist.lua` 不是数据，而是 **CSV 读取器**——服务器列表**运行期下发**（不随包）。列为：

`ID, Index, IP, Port, GameGUID, Name, State, New`

其中三个字段是**分号/逗号分隔的多值列表**（代码用 `SplitString` 拆）：

```lua
local num,ports   = SplitString(strPort)    -- 多端口
local numIP,IPs   = SplitString(strIP)      -- 多 IP
local uNumIndex,indexs = SplitString(strIndex)
for i=1,uNumIndex do
    if tonumber(indexs[i]) == g_nClientServerIndex then  -- 只保留 Index 含 3 的服
        bSkipServer = false
    end
end
```

`g_nClientServerIndex = 3` 来自 §5 的 `config.lua`，`uNew == 1` 的服务器被选为 `g_DefaultServer`。**即：包内不含任何服务器 IP，服务器表由 CDN/网关下发，客户端只按渠道号筛选。**

这与 MyMatch1 的做法（`MyHttp` 拉 `VerInfo.txt` 后按 `Ver` 选 socket 地址）**是同一套设计思路**，只是载体不同。

> `assets/data/script/json/rpcserver.lua` 是第三方库 **JSONRPC4Lua 0.9.40**（Craig Mason-Jones，MIT）——服务端工具，不是客户端逻辑。

---

## 7. Jumpw 的共用痕迹：三个包都有 `300hero.jumpw.com`

`native_core_strings.txt` 中，**2016、2017、2018 三个包都**出现了同一批字符串：

```
300hero.jumpw.com
http://testactivity.jumpwgame.com/activeusermanager.html?serviceCode=10010007...
http://testactivity.jumpwgame.com/activeusermanager.html?serviceCode=30020001&codeId=%s&w=%d&h=%d
http://payment.ddmoba.com/payordercreate.html?serviceCode=10010007&receivername=%s&amount=%d&orderSource=%s&gameGuid=%d&outsn=%s
```

外加一个已恢复的 protobuf 消息类型：**`Sa2gLoginTypeNotJumpw`**（字段 `kSInfoFieldNumber`、`kNAccountIDFieldNumber`、`kNSessionIDFieldNumber`）——即**「非 Jumpw 登录类型」是协议里的一等公民**，登录类型枚举里天然区分 Jumpw 与非 Jumpw 渠道。

**含义**：三个包的原生核心共享一套 **Jumpw 账号/支付接入层**（`jumpw.com` / `jumpwgame.com`，即《300英雄》所在平台）。这比之前「三包共享引擎与资源」的判断更进一步——**连账号与支付通道都是同一套**。

`ciyuan_2017` 里的账号登录链路（`libgame.so`）：

```
http://testactivity.jumpwgame.com/activeusermanager.html?serviceCode=30020001&codeId=%s&w=%d&h=%d
```

而 2016 的对应串里能看到**明文参数名**：

```
...?serviceCode=10010001&fromCid=10161&VerifyCodeStateKey=%s&VerifyCodeKey=%s&NormalAccount=%s&clientPwd=%s&userPwd=%s
```

`serviceCode` 从 2016 的 `10010001` 演进到 2017/2018 的 `30020001`。

**JNI 侧同样沿袭**：2017 的 `libgame.so` 里仍有 `cn/emagroup/kom/Tombird` 与 `Java_cn_emagroup_kom_Tombird_DoPayCallBack`——2017 包（`com.emagroup.mbzw2.emagroup`）**保留了 2016 的 KOM 命名空间**，dex 里 `Lcn/emagroup/kom/` 还有 20 处引用。这是「次元大作战 = 魔霸之王2」的又一处代码级证据。

---

## 8. EMA / 相关域名总表

| 域名 | 出现位置 | 用途 |
|---|---|---|
| `sdk.emagroup.cn` | 2016 dex + developerInfo.xml | 老 SDK 后端（`/esdk_api/`、`/gather/info/`、`/pay/`、`/sys/version`） |
| `esdk2.emagroup.cn` | 2016 developerInfo.xml（`standby_domain_name`） | 老 SDK 备用域 |
| `api.emagroup.cn` / `dev.api.` / `test.api.` | 2017 dex | 新 SDK `/ema-platform/*`（正式 / 开发 / 测试） |
| `kom.cdn.emagroup.cn` | 2016 `version.json`、2017 `version.json` | 资源 CDN（`/Android/`、`/moba02/Android/`） |
| `cdn.emagroup.cn` | MyMatch1 `MyHttp.cs` | 通用 CDN（`/mymatch/android/VerInfo.txt`） |
| `games.emagroup.cn:5555` | MyMatch1 `VerInfo.txt` | socket 网关（**目标包中不存在**） |
| `payment.ddmoba.com` | 2016 developerInfo.xml（OAuth）、libtombird.so | 支付 / OAuth 重定向 |
| `payment2.ddmoba.com` | 2017 `config.lua`（`g_auUrl`，pro） | 活动管理器 |
| `payment.kingofmoba.com` | 2017 `activity_ui.lua:1302` | 活动管理器（另一域） |
| `120.92.63.244` | 2017 `config.lua`（注释 `--test`） | 活动管理器测试环境 |
| `300hero.jumpw.com` | **三包原生库** | Jumpw 账号体系 |
| `testactivity.jumpwgame.com` | **三包原生库** | Jumpw 账号 / 激活接口 |
| `download.jumpw.com/ciyuan/Android/` | 2017 `version_copy.json` | 资源 CDN（备用） |

**资源 CDN 命名链**（`version.json` → `Url` 字段）：

| 包 | `version.json` | `version_copy.json` |
|---|---|---|
| 2016 | `{"Res":63,"App":20,"Url":"http://kom.cdn.emagroup.cn/Android/"}` | — |
| 2017 | `{"Res":76,"App":216,"Url":"http://kom.cdn.emagroup.cn/moba02/Android/"}` | `{"Res":999,"App":999,"Url":"http://download.jumpw.com/ciyuan/Android/"}` |

`kom` → `moba02` → `ciyuan` 是**同一产品线三代内部代号**的完整链条：`kom`=KingOfMoba=魔霸之王，`moba02`=魔霸之王2=次元大作战，`ciyuan`=次元。注意 2017 的 `version_copy.json` 把 `Res/App` 写成 **999/999**（占位哨兵值）并指向 Jumpw CDN——这是**切渠道用**的备用配置。

---

## 9. MyMatch1 自有协议（供对比，**勿与目标包混同**）

`Assets/_Scripts/FrameWork/NetWorkManager/` 是 MyMatch1 自己的 C#/Lua 双端网络层，记录在此仅为**避免误判**：

- `Protocal.cs`：`Connect=101`、`Exception=102`、`Disconnect=103`
- `SocketClient.cs`：`TcpClient` + `NetworkStream`，**2 字节大端长度前缀 + 载荷**，载荷首部为 `int16 mainId`：

```csharp
ushort msglen = (ushort)message.Length;            // 写：长度
byte[] temp = BitConverter.GetBytes(msglen); Array.Reverse(temp);   // 转大端
...
ushort messageLen = (ushort)BitConverter.ToInt16(temp, 0);          // 读：长度
int mainId = buffer.ReadShort();                                    // 头两个字节 = 协议号
NetworkManager.AddEvent(mainId, buffer);
```

- C# 侧把事件推给 Lua：`Util.CallMethod("Network", "OnSocket", buffer.Key, buffer.Value)`；心跳 `ClientHeartBeat`，10 s 判坏网、20 s 回登录。

**目标包用的是 Snake 引擎自带的协议栈 + protobuf**（142 消息 / 1263 字段号，见 [README](../README.md#还原之后还有第二层protobuf-配置表)），与本节的 2 字节长度 + `int16 mainId` **不是同一套**。没有证据表明两侧共用协议实现。

---

## 10. 对本次逆向的实际增量

1. **解释了 EMA SDK 的世代关系**（§4）：2016 内嵌老 SDK → 2017 独立 `com.emagroup.sdk` + `/ema-platform/*` → 2018 彻底移除。此前只能看到一堆域名，现在有了可供对照的实现分层。
2. **补上了 2017 的登录/渠道语义**（§5）：`eLoginType_Ema` / `eLoginType_Spark` / `g_nSDKNew` / `CYDZZ_*` 内购号，说明 2017 包在「EMA 与 Spark 两条渠道」间靠配置切换。
3. **确认了服务器表是运行期下发的**（§6）：包内无服务器 IP，`serverlist.lua` 只是 CSV 读取器——这为「为什么包内找不到目标服务器地址」提供了机制性答案，也说明**离线静态分析不可能恢复服务器列表**。
4. **把 Jumpw 的共用范围从「引擎+资源」扩展到「账号+支付」**（§7），并拿到 `Sa2gLoginTypeNotJumpw` 这个协议级证据。
5. **给出 `ema_app_id=3` 等平台侧标识**（§4.1），可用于把三个包与 EMA 平台上的具体应用对应起来。

---

## 11. 未能确认 / 局限

- **`sdmb` 未解析**：`com.mius.sdmb.sdk.SdkApi` 中的 `sdmb` 拼不出对应产品名，未在任何检索中找到解释。
- **`Mius` 与 EMA 的关系未确认**：`Mius` 是 MyMatch1 的 companyName，也可能只是作者个人名号；无法确认它是否为 EMA 的研发主体。
- **MyMatch1 是否真正上线**：能证明的是它**按 EMA 渠道配置过**（`cdn.emagroup.cn/mymatch/android/`、`NEWEMA` 宏、`APPSTORE` 宏）。没有证据表明该游戏实际发行过。
- **`otherData: 1000`**、渠道 `idChannel=404`、`ReceivedChanelId == 207`（`IsTBT`）的具体渠道名未确认。
- **`eLoginType_Spark`** 的 `Spark` 指向哪家未确认。
- **`ema_app_key` / `privateKey`** 是包内**明文**配置，本文只作为格式证据原样记录；未用于任何请求，也未验证其当前有效性。
- **未连接任何服务器**：本文全部为离线静态分析。所有域名/IP 仅作字符串证据，**不代表其当前可用**（多数应已失效）。

---

## 12. 复现方法

**三个目标包侧**（需自备 APK 并先跑完主流水线）：

```bash
python apk_analysis/analyze_static.py          # 产出 {slug}/dex_strings.txt、network_strings.json
python apk_analysis/decode_resources.py        # 产出 decoded/assets/{version.json,config/config.lua,developerInfo.xml}
grep -rn 'emagroup\|ddmoba\|jumpw' apk_analysis/*/network_strings.json
grep -n  'Lcom/emagroup/sdk/'        apk_analysis/ciyuan_2017/dex_strings.txt | wc -l   # 251
```

**MyMatch1 侧**（公开仓库，直接读）：

```bash
base=https://raw.githubusercontent.com/nick-yangzj/MyMatch1/master
curl -s $base/Assets/_VerInfo/VerInfo.txt
curl -s $base/Assets/_Scripts/FrameWork/Http/MyHttp.cs
curl -s $base/Assets/_Scripts/GameLogic/Sdk/EmaAndroidSDK/SDKEMAController.cs
curl -s $base/Assets/_Scripts/GameLogic/Sdk/EmaAndroidSDK/SdkForAndroid.cs
curl -s $base/Assets/_Scripts/FrameWork/NetWorkManager/SocketClient.cs
```

**DEX 字符串导出**由 `analyze_static.py` 完成（自实现 AXML/ARSC 解析 + DEX 字符串提取），无需外部工具。
