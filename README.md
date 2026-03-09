# AutoISO

将 qBittorrent 下载完成的蓝光原盘（BDMV）或本地文件夹打包成 ISO，并可选地通过 CloudDrive2 挂载目录上传到网盘。支持自动发现完成种子、手动从 qB 或本地目录创建任务。

---

## 项目介绍

### 功能概览

- **自动 / 手动任务**：从 qBittorrent 已完成种子或本地 BDMV 目录创建打包任务。
- **BDMV → ISO**：使用 xorriso 制作符合 UDF 的 ISO，便于归档或上传。
- **CloudDrive2 上传**：将生成的 ISO 写入挂载目录，由 CloudDrive2 接管上传到网盘。
- **排队与并行**：打包阶段单任务排队执行；上传阶段多任务可并行。
- **Web 管理界面**：仪表盘、任务列表、状态筛选、设置（qB / CloudDrive2 / 自动导入模式）等。

### 依赖服务

- **qBittorrent**：提供已完成种子的信息与源路径，需开启 Web UI。
- **CloudDrive2**：挂载网盘目录，AutoISO 将 ISO 写入该目录后由 CloudDrive2 负责上传。
- **xorriso**：用于制作 ISO（Docker 镜像内已包含）。

---

## 终端用户部署指南

### Docker 部署注意事项

**挂载与 qB、CloudDrive2 完全一致（必读）：**

AutoISO **不做路径转换**。它直接使用 qBittorrent 返回的下载路径读取源文件，并直接向你在「设置」里填写的 CloudDrive2 挂载路径写入 ISO。因此，AutoISO 容器内的路径必须与 qB 容器、CloudDrive2 容器**完全一致**：

- **qB 下载目录**：若你的 qB 容器里下载目录是 `/downloads`（例如 `-v /宿主机/qb:/downloads`），则 AutoISO 也必须用**相同的容器内路径**挂载同一宿主机目录，例如 `-v /宿主机/qb:/downloads`。
- **CloudDrive2 挂载目录**：若 CD2 容器里挂载点是 `/clouddrive`（例如 `-v /宿主机/cd2:/clouddrive`），则 AutoISO 也必须用**相同的容器内路径**挂载同一宿主机目录，例如 `-v /宿主机/cd2:/clouddrive`。你在 Web 设置里填写的「挂载目标路径」即为该容器内路径（如 `/clouddrive/我的上传`）。

否则 AutoISO 会找不到 qB 的源文件，或写入的 ISO 不在 CD2 可见的目录内。

### 部署容器

请将下面的宿主机路径换成你实际使用的目录（与 qB、CD2 容器使用相同宿主机路径，容器内路径与 qB、CD2 保持一致），再执行。

```bash
docker run -d \
  --name autoiso \
  -p 7150:7150 \
  -v /opt/autoiso/data:/app/data \
  -v /宿主机/qb下载目录:/容器内与qB一致的路径 \
  -v /宿主机/cd2挂载目录:/容器内与CD2一致的路径 \
  --restart unless-stopped \
  narapeka/autoiso:latest
```

**示例**

```bash
docker run -d \
  --name autoiso \
  -p 7150:7150 \
  -v /volume1/docker/autoiso/data:/app/data \
  -v /volume2/downloads:/downloads \
  -v /volume1/CloudDrive/:/CloudNAS \
  --restart unless-stopped \
  narapeka/autoiso:latest
```

**访问界面：**

在浏览器打开：**http://\<宿主机 IP 或域名\>:7150**

首次使用请在「设置」中填写 qBittorrent、CloudDrive2 的地址与认证信息，以及挂载目标路径；在仪表盘可开启「qB 监控」实现自动发现完成种子。

### 3. 数据目录与持久化

- 容器内数据目录为 **`/app/data`**
- 挂载后，配置、数据库与日志位于宿主机目录下，例如：`config.yaml`、`autoiso.db`、`logs/` 等。

