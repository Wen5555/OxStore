# OxStore 第二次评审前验收核对

执行日期：2026-10-18（Asia/Shanghai）。执行：张耀文提出完善任务，Codex辅助核对、补充脚本和实际测试；录屏由本人手动完成，尚待补充。

## 1. 本轮结果

| 项目 | 结果 | 实际证据 |
| --- | --- | --- |
| 后端单元测试与打包 | PASS；50项，失败/错误/跳过均为0；生成shop-0.1.0.jar | [JUnit汇总与逐项结果](evidence/acceptance-2026-10-18/junit-results.json) |
| 真实Docker/API | PASS；28项检查，含新增D22～D26 | [原始结果与脱敏请求](evidence/acceptance-2026-10-18/docker-results.json) |
| 接口基本场景 | 19/19个方法/路由组合实际执行 | 上述JSON的covered_endpoints与requests |
| 隔离与清理 | 随机项目、临时密码、新数据卷；结束后无本次容器或卷残留 | [环境与镜像身份](evidence/acceptance-2026-10-18/environment.json) |
| 本次录屏 | 待本人手动完成 | 尚无本次录屏链接 |

本轮后端运行Microsoft OpenJDK17.0.16、Maven3.9.12；Docker Engine29.8.2、Compose5.5.1。Maven离线尝试因仓库标识和依赖缓存不完整失败，随后沿用已验证的阿里云public源，通过任务内settings联网执行clean verify成功；未修改全局Maven配置。

## 2. 源码与镜像对应

本轮开始源码提交为d64398b7a464e89cb1852938c453b2411bd9ca11。运行镜像沿用0.1.0-docker.1：已逐个核对镜像ID与原manifest相同，且192d8e4至本轮HEAD的backend/src、frontend/src、POM与前端依赖文件无差异。本轮修改测试脚本和文档，没有重新构建应用镜像。

28项检查由当前更新后的scripts/verify_docker_release.py执行，覆盖新建实例、Nginx、实际HTTP、MySQL、应用重启与容器重建。测试脚本身份和精确镜像ID记录于environment.json，原23项历史结果仍保留原日期。

## 3. 新增或加强的检查

- 后台当前商品接口与未售商品历史详情拒绝。
- 已售商品历史详情与完整记录一致，分页从1开始。
- 非队首开始交易被拒绝；姓名与电话修改后值正确、排位不变；交易中修改/撤销拒绝；缺少交易尝试ID返回400。
- 单个买家重排后仍可凭原码查询，并获得新的交易尝试ID。
- DISCARD使原码失效，空队列恢复在售且保留历次失败记录。
- 恢复在售后可重新提交意向；错误口令拒绝。

## 4. 材料与剩余项

构建手册、源码包、Docker离线包、需求规格、测试清单、自动化脚本和本轮结果已有公开文件或待推送文件。Wiki验收页逐类关联这些材料；正式提交与教师结论以实际接收为准。

本次录屏暂缓，由张耀文手动录制并补入验收页。未执行全部真实UI页面路径、压力并发或正式服务器验证；19接口基本场景通过不等于穷举全部输入。BUG-002备注字段仍需R1确认。本次不代其他组员填写未核实贡献、不编造工时、PPT或教师意见。

## 5. 复验

按照[自动化运行手册](automation_runbook.md)准备独立配置目录并执行；本轮入口为：

```powershell
python scripts/package_docker_release.py prepare --output .work/acceptance-bundle-20261018
python scripts/verify_docker_release.py --bundle .work/acceptance-bundle-20261018 --output docs/test/evidence/acceptance-2026-10-18
```

复验使用新的目录名，保留本轮原始JSON。操作日志不含展开后的环境变量，仅在本地留存。
