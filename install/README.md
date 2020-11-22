# **监控部署方案安装脚本说明**

> 为方便部署，提供一些常用监控组件一键式安装启动脚本

- 主要包括
  - [ ] node_exporter 安装脚本
  - [x] blackbox_exporter 安装脚本

## **blackbox**
> blackbox_安装启动脚本依赖 `systemd` 和 `docker` ， `systemd` 用于自启动设置， `blackbox_exporter` 采用 `docker` 安装。注意脚本执行需要 `root` 权限。

### **使用**
- **git**
  ```
  git clone https://github.com/shenchucheng/prometheus.git
  cd prometheus/install
  chmod u+x ./blackbox_install.sh
  ./blackbox_install.sh # 非 root 用户 sudo ./blackbox_install.sh
  ```


- **参数**
    - 执行 `./blackbox_install.sh -h` 查看帮助信息
    ```
    Usage:
    ./blackbox_install.sh [-p port] [-d configDir] [-f filename] [-v version] [-n name]  
    Description:
        port：     宿主机映射端口 默认 9115
        configDir：配置文件挂载目录 默认 /etc/prometheus/blackbox
        filename： 配置文件名 默认 blackbox.yml
        version:   blackbox_exporter docker 镜像标签 默认 v0.18.0 
        name：     docker启动容器名 默认 blackbox_exporter
    ```
    - 自定义参数示例：（在 `install` 目录下）
      ```
      ./blackbox_install.sh -p 19115 -d /tmp/blackbox -n test_blackbox 
      ```
      - 映射 `blackbox` 服务端口至宿主机端口 `19115`
      - 挂载配置文件目录到宿主机的 `/tmp/blackbox` 目录下
      - 设置 `blackbox` 的 `docker` 容器名为 `"test_blackbox"`