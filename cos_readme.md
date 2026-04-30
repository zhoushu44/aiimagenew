# COS / CDN 配置教程

这份文档用于说明本项目如何把生成图片上传到腾讯云 COS，并通过 CDN 使用 HTTPS 地址访问，避免图片堆在服务器本地，也避免浏览器因为 `http://` 图片资源显示不安全。

## 1. 当前项目的图片链路

```text
用户生成图片
  -> Flask 后端拿到图片二进制
  -> 后端使用 .env 里的 COS 密钥上传到腾讯云 COS
  -> 上传成功后返回图片 URL
  -> 如果配置了 CDN 域名，返回 https://CDN域名/文件路径
  -> 前端直接展示这个 HTTPS 图片地址
```

当前代码里 COS 的核心逻辑在：

- [cos_utils.py](file:///c:/Users/zhou/Desktop/aiimagenew/cos_utils.py)
- [app.py](file:///c:/Users/zhou/Desktop/aiimagenew/app.py)

## 2. COS 和 CDN 的分工

### COS 是什么

COS 是腾讯云对象存储，用来保存项目生成后的图片文件。

你可以理解为：

```text
COS = 云端文件仓库
```

### CDN 是什么

CDN 是内容分发网络，用来加速图片访问，并且可以提供 HTTPS 域名访问。

你可以理解为：

```text
CDN = 加速访问层
```

### 项目推荐架构

```text
Flask 后端上传图片到 COS
浏览器访问 CDN HTTPS 图片地址
CDN 回源到 COS 取文件
```

也就是：

```text
用户浏览器 -> https://aiimg.86969678.xyz/xxx.jpg -> CDN -> COS
```

## 3. 项目需要的 .env 配置

项目读取下面 5 个环境变量：

```env
COS_SECRET_ID=你的腾讯云SecretId
COS_SECRET_KEY=你的腾讯云SecretKey
COS_REGION=ap-guangzhou
COS_BUCKET=你的COS桶名
COS_CDN_DOMAIN=你的CDN加速域名
```

你当前这套配置格式类似：

```env
COS_SECRET_ID=你的腾讯云SecretId
COS_SECRET_KEY=你的腾讯云SecretKey
COS_REGION=ap-guangzhou
COS_BUCKET=aiimg-1318449123
COS_CDN_DOMAIN=aiimg.86969678.xyz
```

注意：

- `COS_SECRET_ID` 和 `COS_SECRET_KEY` 是敏感密钥，只能放在后端 `.env`。
- 不要把密钥写到前端 JS。
- 不要把真实密钥提交到公开仓库。
- `.env` 修改后需要重启 Flask 或容器，运行中的 Python 进程不会自动重新读取旧文件。

## 4. 当前代码如何读取 .env

COS 配置读取位置是 [cos_utils.py](file:///c:/Users/zhou/Desktop/aiimagenew/cos_utils.py)。

当前逻辑是：

```text
1. cos_utils.py 启动时先加载项目根目录 .env
2. 从 .env 读取 COS_SECRET_ID
3. 从 .env 读取 COS_SECRET_KEY
4. 从 .env 读取 COS_REGION
5. 从 .env 读取 COS_BUCKET
6. 从 .env 读取 COS_CDN_DOMAIN
7. 初始化腾讯云 COS 客户端
8. 上传成功后拼接 HTTPS 图片 URL
```

关键点：

```text
COS_CDN_DOMAIN 有值：返回 https://COS_CDN_DOMAIN/文件路径
COS_CDN_DOMAIN 为空：返回 https://COS_BUCKET.cos.COS_REGION.myqcloud.com/文件路径
```

所以只要 `COS_CDN_DOMAIN=aiimg.86969678.xyz`，返回的图片地址就是：

```text
https://aiimg.86969678.xyz/generated/202604/taskid/01-main.jpg
```

## 5. 腾讯云 COS 从 0 到 1 配置教程

### 第一步：创建 COS 存储桶

进入腾讯云控制台：

```text
腾讯云控制台 -> 对象存储 COS -> 存储桶列表 -> 创建存储桶
```

建议填写：

```text
所属地域：广州
地域代码：ap-guangzhou
存储桶名称：例如 aiimg
访问权限：按项目需要配置为可公开读图
```

创建后腾讯云会生成完整桶名，通常格式是：

```text
aiimg-1318449123
```

这个完整桶名要写入 `.env`：

```env
COS_BUCKET=aiimg-1318449123
```

### 第二步：确认地域代码

COS 地域必须和桶所在地域一致。

常见地域示例：

```text
广州：ap-guangzhou
上海：ap-shanghai
北京：ap-beijing
南京：ap-nanjing
成都：ap-chengdu
中国香港：ap-hongkong
新加坡：ap-singapore
```

如果桶在广州，就写：

```env
COS_REGION=ap-guangzhou
```

地域写错时，常见报错是：

```text
签名错误
桶不存在
上传失败
403 / 404
```

### 第三步：创建 API 密钥

进入腾讯云控制台：

```text
右上角账号 -> 访问管理 CAM -> 访问密钥 -> API 密钥管理 -> 新建密钥
```

你会拿到：

```text
SecretId
SecretKey
```

写入 `.env`：

```env
COS_SECRET_ID=你的SecretId
COS_SECRET_KEY=你的SecretKey
```

建议：

- 正式环境最好使用子账号密钥。
- 子账号只授予当前 COS 桶的上传、读取、删除权限。
- 不建议长期使用主账号全权限密钥。

### 第四步：配置对象读取权限

项目上传图片时会设置对象 ACL 为：

```text
public-read
```

这样前端才能通过图片 URL 直接展示图片。

如果你希望更严格，也可以在腾讯云里用“私有桶 + CDN 鉴权”的方式，但那会增加签名 URL、鉴权配置和过期时间控制，当前项目默认走公开读图方案，简单稳定。

## 6. CDN 从 0 到 1 配置教程

### 第一步：准备 CDN 域名

你需要准备一个图片域名，例如：

```text
aiimg.86969678.xyz
```

建议用子域名，不要直接用主站域名。

例如：

```text
主站：www.86969678.xyz
图片 CDN：aiimg.86969678.xyz
```

### 第二步：添加 CDN 加速域名

进入腾讯云控制台：

```text
腾讯云控制台 -> 内容分发网络 CDN -> 域名管理 -> 添加域名
```

建议配置：

```text
加速域名：aiimg.86969678.xyz
业务类型：静态加速
源站类型：COS 源
源站：选择你的 COS 桶 aiimg-1318449123
回源协议：HTTPS 或协议跟随
```

如果控制台没有直接选择 COS 源，也可以使用 COS 原始域名作为源站：

```text
aiimg-1318449123.cos.ap-guangzhou.myqcloud.com
```

### 第三步：配置 DNS 解析

CDN 添加成功后，腾讯云会给你一个 CNAME 地址，类似：

```text
aiimg.86969678.xyz.cdn.dnsv1.com
```

然后去你的域名 DNS 控制台添加解析：

```text
主机记录：aiimg
记录类型：CNAME
记录值：腾讯云 CDN 提供的 CNAME 地址
```

配置后等待 DNS 生效。

### 第四步：开启 HTTPS

为了避免浏览器提示不安全，CDN 域名必须开启 HTTPS。

进入：

```text
腾讯云 CDN -> 域名管理 -> aiimg.86969678.xyz -> HTTPS 配置
```

推荐开启：

```text
HTTPS：开启
证书：申请免费证书或上传已有证书
HTTP/2：开启
强制 HTTPS：开启
HTTP 跳转 HTTPS：开启
```

开启后，图片应该使用：

```text
https://aiimg.86969678.xyz/文件路径
```

而不是：

```text
http://aiimg.86969678.xyz/文件路径
```

### 第五步：配置 CDN 回源和缓存

推荐配置：

```text
回源 Host：COS 桶默认域名或腾讯云自动设置
回源协议：HTTPS
缓存规则：图片文件缓存 30 天或更长
```

常见图片后缀：

```text
jpg jpeg png webp gif bmp
```

可以设置较长缓存，因为项目生成图片路径里包含任务 ID，不容易出现同名覆盖。

### 第六步：配置 CORS

如果前端需要直接下载图片、浏览器本地打包 ZIP，建议在 COS 或 CDN 允许跨域。

COS CORS 推荐配置：

```text
来源 Origin：*
允许方法：GET, HEAD
允许 Header：*
暴露 Header：ETag, Content-Length, Content-Type
缓存时间 MaxAgeSeconds：600
```

如果你只想允许自己的站点访问，可以把 `*` 改成你的主站域名：

```text
https://你的主站域名
```

## 7. 把 CDN 域名写回项目

CDN 配好以后，把域名写到 `.env`：

```env
COS_CDN_DOMAIN=aiimg.86969678.xyz
```

不要写协议头：

```env
COS_CDN_DOMAIN=https://aiimg.86969678.xyz
```

上面这种不推荐，因为代码会自动补 `https://`。

正确写法是：

```env
COS_CDN_DOMAIN=aiimg.86969678.xyz
```

项目最终返回：

```text
https://aiimg.86969678.xyz/文件路径
```

## 8. 如何测试 COS 是否正常

### 测试 1：检查 Python SDK 是否安装

```bash
python -c "import qcloud_cos; print('qcloud_cos ok')"
```

如果缺少依赖，执行：

```bash
python -m pip install -r requirements.txt
```

### 测试 2：检查是否从 .env 读取

```bash
python -c "import cos_utils; print(cos_utils.is_cos_enabled()); print(cos_utils.COS_URL_PREFIX); print(cos_utils.COS_BUCKET); print(cos_utils.COS_REGION)"
```

正常应该看到：

```text
True
https://aiimg.86969678.xyz
aiimg-1318449123
ap-guangzhou
```

### 测试 3：上传并删除测试文件

```bash
python -c "import cos_utils; key='trae-cos-test/healthcheck.txt'; url=cos_utils.upload_to_cos(b'cos env healthcheck', key, 'text/plain'); print(url); cos_utils.delete_from_cos(key); print('deleted')"
```

正常结果：

```text
https://aiimg.86969678.xyz/trae-cos-test/healthcheck.txt
deleted
```

这个测试会上传一个很小的文本文件，然后马上删除。

## 9. 本次实测结果

本地已完成一次连通性测试：

```text
COS enabled: True
URL prefix: https://aiimg.86969678.xyz
Bucket: aiimg-1318449123
Region: ap-guangzhou
Upload: success
Delete: success
```

说明：

```text
.env 读取正常
COS 客户端初始化正常
上传权限正常
删除权限正常
CDN HTTPS URL 拼接正常
```

## 10. 前端为什么能直接显示图片

前端图片处理逻辑在 [workspace.js](file:///c:/Users/zhou/Desktop/aiimagenew/static/js/workspace.js)。

当前逻辑是：

```text
如果后端返回 http:// 或 https:// 开头的完整图片 URL
前端直接使用这个 URL
不会再强制改成本地 /generated/ 路径
```

所以后端返回：

```text
https://aiimg.86969678.xyz/generated/202604/taskid/01-main.jpg
```

前端就会直接：

```html
<img src="https://aiimg.86969678.xyz/generated/202604/taskid/01-main.jpg">
```

## 11. ZIP 下载说明

项目支持批量下载图片。

当前逻辑兼容两种情况：

```text
1. 图片在本地 generated-suites 目录：直接从本地打包
2. 图片在 COS/CDN：通过 HTTPS 图片地址读取后打包
```

如果浏览器直接访问 CDN 图片并打包 ZIP，需要注意 CORS。

如果出现前端下载失败，重点检查：

```text
COS 是否允许 GET
CDN 是否开启 HTTPS
CDN 是否允许跨域
图片 URL 是否能在浏览器新标签页直接打开
```

## 12. 常见问题排查

### 图片上传失败

重点检查：

```text
COS_SECRET_ID 是否正确
COS_SECRET_KEY 是否正确
COS_REGION 是否和桶地域一致
COS_BUCKET 是否是完整桶名
cos-python-sdk-v5 是否安装
```

### 图片返回的是 COS 原始域名，不是 CDN 域名

检查：

```env
COS_CDN_DOMAIN=
```

如果这里为空，项目会回退到 COS 原始域名。

填入 CDN 域名后重启 Flask：

```env
COS_CDN_DOMAIN=aiimg.86969678.xyz
```

### 浏览器显示不安全

原因一般是访问了 `http://`。

图片域名要确保：

```text
CDN 已开启 HTTPS
CDN 已开启 HTTP 自动跳转 HTTPS
项目返回的是 https:// 开头图片地址
```

主站也要用 HTTPS 访问：

```text
https://你的主站域名
```

不要让用户访问：

```text
http://你的主站域名
http://服务器IP:端口
```

### 图片 403

一般是权限问题：

```text
对象不是 public-read
桶策略禁止访问
CDN 鉴权开启但 URL 没带签名
Referer 防盗链配置拦截
```

### 图片 404

一般是路径或源站问题：

```text
文件没有上传成功
CDN 源站指错桶
COS_REGION 写错
COS_BUCKET 写错
CDN 缓存了旧 404
```

可以先在 COS 控制台确认文件是否存在，再刷新 CDN 缓存。

### 修改 .env 后不生效

修改 `.env` 后需要重启：

```text
Flask 开发服务
生产环境进程
Docker 容器
宝塔/1Panel 里的 Python 服务
```

## 13. 推荐上线配置清单

上线前建议逐项确认：

```text
COS_BUCKET 使用完整桶名
COS_REGION 和桶地域一致
COS_SECRET_ID / COS_SECRET_KEY 有上传、读取、删除权限
COS_CDN_DOMAIN 只写域名，不写 https://
CDN 源站指向正确 COS 桶
CDN HTTPS 已开启
CDN HTTP 跳转 HTTPS 已开启
COS 或 CDN CORS 已配置
主站也使用 HTTPS 域名访问
.env 没有提交到公开仓库
```

## 14. 一句话总结

```text
COS 负责存图，CDN 负责 HTTPS 加速访问，项目从 .env 读取配置，上传后返回 https://CDN域名/文件路径 给前端直接展示。
```
