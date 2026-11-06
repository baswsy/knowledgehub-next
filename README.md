# 知学 KnowledgeHub 2.0

面向课程复习的AI学习工作台。延续初版KnowledgeHub白色侧栏、蓝色主色与卡片布局，将本地迭代版检索问答、授权、记忆、预算和视频字幕能力接入独立网页。

## 网页

`docs/` 是无需构建的响应式前端，可通过GitHub Pages部署。本地模式支持笔记新建、编辑、搜索、导入文字、导出、视频链接管理和学习偏好保存，数据位于当前浏览器localStorage。无模型密钥，无模拟AI回复。连接服务端后使用独立服务器工作区，不自动同步浏览器资料；连接前可导出备份。

## GitHub Pages发布

新建仓库 `knowledgehub-next`，上传本目录全部文件。打开Settings → Pages → Source选择GitHub Actions，推送main后由`.github/workflows/pages.yml`发布。也可直接选择Deploy from a branch，main分支、/docs目录。前端地址通常为https://baswsy.github.io/knowledgehub-next/，以GitHub实际返回地址为准。

## Python后端

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r study_assistant/requirements.lock.txt
# 在环境或study_assistant/.env配置模型密钥
export DEEPSEEK_API_KEY=你的密钥
export STUDY_ACCESS_PASSWORD=你设置的强口令
export STUDY_WEB_ORIGINS=https://baswsy.github.io
PYTHONPATH=study_assistant .venv/bin/uvicorn web_api:app --app-dir study_assistant --host 0.0.0.0 --port 8000
```

网页连接设置中填写HTTPS后端地址和访问口令。口令仅放页面内存；刷新需重新连接。GitHub Pages只发布前端，Python服务须独立部署。当前单工作区，不提供多用户资料隔离；仅向可信使用者分享访问口令。公网需HTTPS、请求限流与访问控制。

功能：带引用问答、MCP执行记录、预算信息、笔记、PDF/Word上传、图谱、大纲、公开字幕读取和字幕上传。字幕总结在AI对话中选择对应资料执行。图谱可查看概念详情，前端目前使用静态关系布局；完整拖拽导出仍可使用Streamlit入口。刷新会清除网页聊天展示，服务端保存会话记录。

`Dockerfile`默认启动原Streamlit；独立网页后端设置环境变量`APP_MODE=api`，并配置`PORT=8000`和前端来源`STUDY_WEB_ORIGINS`。启动脚本沿用持久化目录。部署前参见deploy/README.md。

## 验证边界

包含预算、权限、字幕、上下文和存储自动测试。浏览器自动化当前不可用，视觉和交互未完成浏览器验收；线上模型、公开字幕及Pages发布状态须实际验证。前端存在不代表AI后端已上线。
