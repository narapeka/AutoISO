<script setup lang="ts">
// 帮助页：中文使用指南，无逻辑
</script>

<template>
  <section class="view help-view">
    <div class="view-header">
      <h1>帮助</h1>
    </div>

    <div class="help-content">
      <section class="panel">
        <div class="panel-header"><h2>AutoISO 是什么？</h2></div>
        <p>AutoISO 用于将 qBittorrent 下载完成的蓝光原盘（BDMV）或本地文件夹打包成 ISO，并可选地通过 CloudDrive2 挂载目录上传到网盘。支持自动发现完成种子、手动从 qB 或本地文件夹创建任务。</p>
      </section>

      <section class="panel">
        <div class="panel-header"><h2>仪表盘</h2></div>
        <p>仪表盘用于查看运行状态与最近日志。</p>
        <ul>
          <li><strong>qBittorrent / CloudDrive2</strong>：显示与 qB、CloudDrive2 服务的连接是否正常。</li>
          <li><strong>队列</strong>：当前处于「待处理」状态、等待打包的任务数量。</li>
          <li><strong>活动上传</strong>：正在写入挂载目录或由 CloudDrive2 上传中的任务数量。</li>
          <li><strong>日志</strong>：最近的操作与系统事件，便于排查问题。</li>
        </ul>
      </section>

      <section class="panel">
        <div class="panel-header"><h2>任务与状态</h2></div>
        <p>在「任务」页可以查看、筛选、操作所有任务。任务状态含义如下：</p>
        <ul>
          <li><strong>已导入</strong>：仅在使用「仅导入」模式时出现。任务已创建但未进入执行队列，需要你点击「开始」后才会开始打包。</li>
          <li><strong>待处理</strong>：任务已在队列中，系统会按创建顺序自动开始打包。</li>
          <li><strong>打包中</strong>：正在校验源目录并生成 ISO 文件。</li>
          <li><strong>已打包</strong>：ISO 已生成。若未开启自动上传，可手动点击「上传」；若已开启则会自动进入下一步。</li>
          <li><strong>写入挂载目录中</strong>：正在把 ISO 写入 CloudDrive2 挂载目录，或等待 CloudDrive2 识别并接管上传。</li>
          <li><strong>CloudDrive2 上传中</strong>：文件已由 CloudDrive2 接管，正在上传到网盘。</li>
          <li><strong>已完成</strong>：上传完成，本地打包副本已清理。</li>
          <li><strong>失败 / 已取消</strong>：任务异常结束或被人为取消，可点击「重试」重新入队。</li>
        </ul>
        <p class="help-note">打包阶段是<strong>排队执行</strong>的：同一时间只会有一个任务在打包，按「待处理」的创建顺序依次处理。CloudDrive2 上传阶段<strong>可并行</strong>，多个任务可同时上传。</p>
      </section>

      <section class="panel">
        <div class="panel-header"><h2>任务来源与操作</h2></div>
        <ul>
          <li><strong>qB 自动任务</strong>：在设置中开启「qB 监控」后，系统会按轮询间隔检查 qBittorrent 已完成的种子；符合分类/标签过滤的会自动创建任务（根据「自动导入模式」为已导入或待处理）。</li>
          <li><strong>qB 手动任务</strong>：在「任务」页点击「从 qB 添加」，从已完成种子列表中选择一个创建任务。</li>
          <li><strong>文件夹手动任务</strong>：点击「从文件夹添加」，选择本地包含 BDMV 的目录创建任务。</li>
        </ul>
        <p>对「已导入」任务可点击<strong>开始</strong>将其变为待处理；对进行中的任务可<strong>取消</strong>；对失败或已取消的任务可<strong>重试</strong>（重新入队打包并上传）。</p>
      </section>

      <section class="panel">
        <div class="panel-header"><h2>设置说明</h2></div>
        <ul>
          <li><strong>qBittorrent</strong>：填写 qBittorrent Web UI 的地址、用户名、密码。分类过滤、标签过滤仅对自动发现的种子生效，留空表示不过滤。</li>
          <li><strong>CloudDrive2</strong>：填写 CloudDrive2 的地址与认证信息。「挂载目标路径」为 ISO 要复制到的目录（即 CloudDrive2 挂载到本地的路径）。上传带宽分配用于在有多任务上传时限制 qBittorrent 的上传速度，为 CloudDrive2 留出带宽。</li>
          <li><strong>自动导入模式</strong>（在仪表盘或相关设置中）：<strong>仅导入</strong>表示新发现的种子只创建为「已导入」任务，需手动点开始；<strong>仅打包</strong>表示自动打包但不自动上传；<strong>打包并上传</strong>表示自动打包且自动写入挂载并交由 CloudDrive2 上传。</li>
        </ul>
      </section>
    </div>
  </section>
</template>

<style scoped>
.help-content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.help-content .panel {
  padding: 1.25rem 1.5rem;
}
.help-content h2 {
  margin: 0 0 0.75rem;
  font-size: 1.1rem;
}
.help-content p {
  margin: 0 0 0.6rem;
  color: #cbd5e1;
  line-height: 1.6;
}
.help-content p:last-child {
  margin-bottom: 0;
}
.help-content ul {
  margin: 0 0 0.6rem;
  padding-left: 1.35rem;
  color: #cbd5e1;
  line-height: 1.65;
}
.help-content ul:last-child {
  margin-bottom: 0;
}
.help-content li {
  margin-bottom: 0.35rem;
}
.help-content li:last-child {
  margin-bottom: 0;
}
.help-note {
  margin-top: 0.75rem;
  padding: 0.6rem 0.85rem;
  background: rgba(37, 99, 235, 0.12);
  border-radius: 10px;
  font-size: 0.9rem;
}
</style>
