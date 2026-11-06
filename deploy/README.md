# 知学部署包

当前为单用户共享工作区。公网运行须设置STUDY_ACCESS_PASSWORD，所有持有密码者访问同一份资料。

## Docker服务器

在study_assistant/.env中设置DEEPSEEK_API_KEY、STUDY_ACCESS_PASSWORD。不要提交密钥。
执行docker compose up -d --build，访问服务器本机127.0.0.1:8501；公网入口需配置HTTPS反向代理，支持WebSocket。数据保存在zhixue_data卷，不随容器替换删除。

## Render

将解压后的源码推送至自己的仓库，通过Blueprint读取render.yaml，填写模型密钥和访问密码。配置包含付费实例和5GB持久化盘，创建前核对平台费用。仅持久化/app/persistent，启动脚本将资料、数据库、模型缓存、运行记录和导出目录链接到该磁盘。

## Vercel

当前不是Vercel Functions入口，不能直接将Streamlit启动命令当作函数部署。若采用Vercel，建议重写为Next.js前端并连接独立Python API服务；持久化数据库与文件存储也需按托管架构规划。

## 验证状态

Python编译、13项单元测试和启动脚本语法检查通过。本机没有Docker，镜像构建和云端运行尚未验证。包内不包含密钥、用户资料、缓存、历史记录或作业文档。首次向量检索会下载中文嵌入模型，需可访问模型下载源。
