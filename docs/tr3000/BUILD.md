# Debian WSL 构建

源码维护目录：`F:\CLionProjects\immortalwrt-mt798x`。
构建目录：`/home/fortern/build/immortalwrt-tr3000-v25.12.2`。

当前进展必须以 `STATUS.md` 为准；本说明不表示厂商驱动构建已通过。

## 环境

使用 Debian 13 WSL 2，普通用户 `fortern` 执行编译。安装依赖时可以使用 sudo。
构建脚本会将 PATH 限定到 Linux 路径，避免 Windows 中带空格的目录影响构建。
eBPF 使用 Debian 的 `/usr/lib/llvm-19` 工具链，避免重复构建完整 LLVM；
目标系统的 GCC 交叉工具链仍由正式版源码构建。复现时需安装相同的 LLVM 19 工具。
源码仓库应设置 `core.autocrlf=false`、`core.eol=lf`，不改变 Windows Git 的全局设置。

```sh
sudo apt-get update
sudo apt-get install -y build-essential clang-19 llvm-19 flex bison g++ gawk gcc-multilib \
  g++-multilib gettext git libncurses-dev libssl-dev python3 python3-setuptools \
  python3-pyelftools rsync unzip zlib1g-dev file wget curl ca-certificates patch \
  perl swig libelf-dev libfdt-dev device-tree-compiler zstd ccache time jq \
  xz-utils bzip2 pkgconf autoconf automake libtool
```

如本机下载需要代理，在当前 shell 中设置 `http_proxy` 和 `https_proxy`；
不要把代理地址写入固件或提交到仓库。

feeds 仍固定为正式版的原始提交。LuCI 使用 sparse checkout 获取基础模块、协议、主题、
构建文件、防火墙和软件包管理界面，避免获取未选用的第三方插件内嵌数据库。
如后续增加其他 LuCI 应用，需要同步扩展 `scripts/tr3000-feeds.py` 的检出列表。

## 构建入口

```sh
# 官方基线（保留官方无线栈，加 LuCI）
bash /mnt/f/CLionProjects/immortalwrt-mt798x/scripts/tr3000-build.sh baseline

# 厂商版本：构建当前已提交的维护分支
bash /mnt/f/CLionProjects/immortalwrt-mt798x/scripts/tr3000-build.sh vendor
```

`TR3000_SOURCE`、`TR3000_BUILD` 可覆盖源码和构建路径。
厂商构建拒绝未提交的源码工作树；不会覆盖构建目录中已修改的受跟踪文件。
只有源码仓库是修改入口，WSL 构建副本用于检出已提交版本和编译。

完整构建默认最多使用 8 个并行任务，失败后单线程重试并保存详细日志。
产物导出到 `artifacts/<源码提交>/<模式>-<UTC时间>/`，包括构建退出码、
输入/展开配置、feeds 版本、环境、日志、二进制产物及 SHA-256 清单。
退出码为零表示构建成功，不表示实机验证成功。

## 独立重建

使用不同的 `TR3000_BUILD` 路径构建相同提交。可以复用下载缓存，
不得复用先前的 build_dir 或 staging_dir 作为干净重建证据。
对比固件和软件包清单并记录差异；不预先承诺产物逐字节相同。

```sh
# 固定候选提交，避免两次构建之间分支移动。
candidate=$(git -C /mnt/f/CLionProjects/immortalwrt-mt798x rev-parse HEAD)
TR3000_BUILD=/home/fortern/build/immortalwrt-tr3000-v25.12.2-rebuild \
  bash /mnt/f/CLionProjects/immortalwrt-mt798x/scripts/tr3000-build.sh vendor "$candidate"
```

如果提前准备新的 Git 检出，可以把其 `dl` 符号链接到第一次构建的下载缓存，
并以 Git clone 复制固定 feeds 的源码对象缓存。不得复制已编译目录。
两份构建导出记录都必须保留，`source-commit`、feeds、输入配置和展开配置应相同。

## 验证与重放

```sh
python3 /mnt/f/CLionProjects/immortalwrt-mt798x/scripts/tr3000-check-source.py
python3 /mnt/f/CLionProjects/immortalwrt-mt798x/scripts/tr3000-check-replay.py \
  /mnt/f/CLionProjects/immortalwrt-mt798x \
  /home/fortern/build/tr3000-replay-final \
  /mnt/f/CLionProjects/immortalwrt-mt798x/artifacts/validation/replay-final.json
```

重放目录必须不存在，脚本不覆盖已有目录；报告包含每个提交、基线和最终文件树。
镜像检查由构建入口自动运行，验证固件元数据、根文件系统、模块版本和无线固件哈希。
查看 `artifacts/validation/DELIVERY.md` 获取最终交付记录；它和编译日志属于构建产物，
保留在本地，按 `.gitignore` 规则不纳入源码提交。

将来重放本次适配系列时，可以取交付记录中的最后提交，使用
`git rev-list --reverse v25.12.2..<最后提交>` 获取完整顺序；不要只挑最后几个修复提交。
本轮仅验证 v25.12.2 基线，其他正式版仍需重新核对和适配。
