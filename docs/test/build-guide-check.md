# 构建手册核对记录

日期：2026-10-18（Asia/Shanghai）。对应请求：完善OxStore构建文档。执行：Codex辅助；本人阅读复核待完成。

## 本轮核对

| 项目 | 依据与结果 |
| --- | --- |
| 源码基线 | 本地 main 为 `0de10b821898ca4da4fb4d3eca498c98cd7d7345`，包含PR #3；既有 `outputs/docker-release/` 未跟踪目录保留 |
| 后端命令与产物 | `pom.xml`定义Java17、Spring Boot3.2.5、shop0.1.0及Boot打包插件；Dockerfile执行 `clean verify`，本手册对应JAR路径一致 |
| 前端命令与产物 | `package.json`构建脚本为 `tsc -b && vite build`；锁文件、Dockerfile与手册的 `npm ci`、Node20、dist路径一致 |
| 镜像与编排 | 核对两份Compose的构建/运行用途、平台、镜像标签和不同端口；离线包三镜像版本与打包脚本一致 |
| 完整手册随包 | 实际调用 `package_docker_release.prepare`，向临时目录复制；`build-guide.md`与源码 `docs/build.md`逐字节一致，所需配置与脚本存在，未产生运行 `.env`；临时目录在检查结束后清理 |
| 文档格式与链接 | 检查README、构建手册、运行手册和Docker说明的本地Markdown文件链接存在、代码围栏成对；`git diff --check`通过 |
| 已发布证据 | 读取2026-10-12包的manifest与构建日志；后端历史日志为50项JUnit通过、BUILD SUCCESS。前端保存的最终构建日志使用缓存，不把本轮读取当作重新执行前端编译 |

## 本轮未执行

文档修订：按用户要求，构建手册已移除已发布版本下载、发布历史、课程提交说明及本轮执行记录，正文集中描述项目构建准备、工具、命令、产物和打包方法。本页保留实际核对与执行范围。

- 当前Docker客户端为29.8.2，Compose为5.5.1，Docker Linux引擎管道不存在；没有启动引擎、重新构建镜像、导出大包或重跑容器业务验证。
- 本机默认Java21.0.8、Maven3.9.12（使用Java21）、Node22.15.0、npm11.12.1；这些输出只说明当前工具状态，不证明项目要求的Java17/Node20本机构建已通过。手册推荐容器构建以提供对应版本。
- 未验证全新机器上的工具安装、外部下载地址可用性或端到端重建；未修改Wiki或覆盖已有Release附件。

## 交付入口

- [构建手册](../build.md)
- [运行手册](../runbook.md)
- [2026-10-12 Docker交付版验证](docker-release.md)

这份记录验收的是文档与手册复制集成。应用构建和运行能力仍以对应版本、对应日期的真实执行证据为准。
