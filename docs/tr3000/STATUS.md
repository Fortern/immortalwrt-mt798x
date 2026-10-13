# TR3000 v25.12.2 适配状态

官方基线与首个厂商镜像已经生成并通过内容检查。最终候选版本的构建、独立重建、
提交重放和产物比较记录统一保存于 `artifacts/validation/`；最终交付结论以该目录中的
`DELIVERY.md` 和对应源码提交下的构建记录为准。实机验收始终单独记录。

## 已完成

- Debian 13 WSL 编译依赖安装；源码仓库从正式版建立 `tr3000-v25.12.2-mtk` 分支。
- 仓库 LF 约定、基线设备配置、构建入口与固定 feeds 获取脚本。
- 正式版祖先、文本 LF、脚本执行权限和 feeds 锁定内容检查通过。
- 构建入口通过 Bash 语法与 ShellCheck 检查。
- 已从固定来源分别导入无线组件、HNAT 和无线总线辅助代码，保留来源许可与二进制。
- 补齐参考仓库下载目录中的 datconf 源码压缩包，并记录 SHA-256。
- 已接入厂商 HNAT 数据包与复位路径，排除上游 WED/PPE 对同一硬件的重复管理；Linux 6.12 内核和 HNAT 模块编译通过。
- 已启用目标设备厂商配置，加入保留官方分区布局的设备树、Factory 校准读取、netifd、iwinfo 后端及独立 LuCI 入口。
- 展开配置检查已确认设备、AP/STA、双频、固件及无线驱动互斥选择。
- conninfra 和 warp 已通过 Linux 6.12 模块编译、链接及 APK 封装；iwinfo 厂商后端编译通过。
- 已调整三个平台驱动的 Linux 6.12 remove 回调；新生成无线配置默认禁用。
- 官方补丁在独立 Linux 6.12.103 参考源码目录中完整应用通过。
- Linux `6.12.103` 源码 SHA-256 校验通过：
  `f143aaade8877ba5616e788b4482576db28481bcf557ef537f4fcc3938fc3176`。

## 构建过程记录

GitHub 大批量传输多次出现 `GnuTLS recv error (-9)`、`early EOF`，Windows Git 也出现 TLS 中断。
主仓库通过固定归档和 Git blob 哈希核验恢复后完成精确检出。
feeds 改为直接获取锁定提交，避免额外下载最新分支；五个 feeds 均已验证。
LuCI 采用固定提交的稀疏检出，包含官方界面、构建工具和必要依赖。
官方基线完整构建通过，记录位于：
`artifacts/4fc16f2985a358bd43bb522e43f05395fcbd6ed5/baseline-20261012T142545Z/`。
构建退出码为零，sysupgrade 镜像 13,199,653 字节；元数据包含
`cudy,tr3000-256mb-v1`、`R103` 和正式版版本号。

已根据实际编译错误修复 6.12 的 HNAT、conninfra、warp、mt_wifi 接口、隐藏 WEXT 依赖、
datconf 的 CMake 设置和 APK 包版本格式。关闭参考配置中的可选 MBO 与 WAPP 管理的
MSCS/DABS 扩展；AP/STA、双频、普通 WMM 队列和厂商加速依赖保持启用。

首个厂商镜像源码为 `683c9ad315d1efc16d167e1c129a9e2682b1e290`，
sysupgrade 大小为 14,766,373 字节；元数据、模块与固定固件检查通过。
该轮构建入口的新增检查脚本最初因 ABI 包名和非 root 解包设备节点失败，
修正后单独检查通过，不能将该轮入口退出码改写为零。
最终候选版本必须用修正后的入口重新完整执行，且另有独立干净构建证据。

曾在同一构建目录重叠执行辅助编译和主编译，导致 sed 的配置头不完整。
清理该组件后，单独重编译通过。构建入口已增加目录锁，后续不并发操作同一构建目录。

失败与重试记录位于被 Git 忽略的 `artifacts/4fc16f2985a358bd43bb522e43f05395fcbd6ed5/`。

## 固定来源

- 官方仓库：https://github.com/immortalwrt/immortalwrt
- 正式版标签：`v25.12.2`
- 正式版提交：`4fc16f2985a358bd43bb522e43f05395fcbd6ed5`
- 驱动参考仓库：https://github.com/padavanonly/immortalwrt-mt798x-6.6
- 驱动参考提交：`ec9ef10efc65da1e6d1de4e2c043c0e13d08eed8`
- 目标：`mediatek/filogic`，`cudy_tr3000-256mb-v1`，Linux 6.12。

参考提交不代表用户当前稳定固件的准确源码版本。

## 验证边界

提交重放阶段记录已证明 75 个提交从正式版重放后文件树一致；最终提交如有变化，
必须重新执行重放检查。构建入口会执行配置与镜像检查，成功记录含 `exit-code=0`。
独立重建必须使用新的目录，不能复用工具链、build_dir、staging_dir 或 ccache 结果。
比较结果须记录实际一致项和差异项，不预设逐字节相同。

本轮不刷机。启动、双频 AP、STA 回程、AP/STA 共存、重连、转发和长期稳定性均需另行实机验证。
详细项目见 `HARDWARE-ACCEPTANCE.md`。
