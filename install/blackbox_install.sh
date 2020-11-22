#!/bin/bash
# @Date   : 2020-11-21 21:48:40
# @Author : Shen Chucheng
# MAIL    : chuchengshen@fuzhi.ai
# @Desc   : Blackbox Docker 一键安装启动脚本


# 默认参数
# version blackbox_exporter 版本
version=v0.18.0

# 映射端口
port=9115

# docker 运行容器名
name=blackbox_exporter

# blackbox_exporter 装配置文件目录(挂载目录)
# 宿主机
configdir=/etc/prometheus/blackbox
# docker
dconfigdir=/config

# 配置文件名
filename=blackbox.yml


default_version=$version
default_port=$port
default_configdir=$configdir
default_filename=$filename
default_name=$name
usage() {
    echo "Usage:"
    echo "  $0 [-p port] [-d configDir] [-f filename] [-v version] [-n name]  "
    echo "Description:"
    echo "    port：     宿主机映射端口 默认 $default_port"
    echo "    configDir：配置文件挂载目录 默认 $default_configdir"
    echo "    filename： 配置文件名 默认 $default_filename"
    echo "    version:   blackbox_exporter docker 镜像标签 默认 $default_version "
    echo "    name：     docker启动容器名 默认 $default_name"
    exit -1
}


while getopts hp:d:f:n: option
do
   case "${option}"  in  
                p) port=${OPTARG};;
                d) configdir=${OPTARG};;
                f) filename=${OPTARG};;
                n) name=${OPTARG};;
                v) version=${OPTARG};;
                h) usage;;
                ?) usage;;
   esac
done

# 权限检测
if ! [ "$EUID" = "0" ]; then 
  echo '安装脚本需要 root 权限，请使用 root 用户，或者 +sudo 执行'
  exit 1
fi

# 环境检测
if ! [ -x "$(command -v docker)" ]; then
  echo '未检测到docker程序，请先安装docker' >&2
  exit 1
fi

if ! [ -x "$(command -v systemctl)" ]; then
  echo '未检测到systemctl工具，请先安装systemd' >&2
  exit 1
fi

if ! [ "$(systemctl is-active docker)" = 'active' ]; then
  echo 'docker 未启动' 
  echo '开始启动docker'
  systemctl start docker.service
  if ! [ "$(systemctl is-active docker)" = 'active' ]; then
    echo 'docker 启动失败' >&2
    exit 1
  fi
  echo '启动docker成功'
fi

# 参数确认
echo "参数："
echo "port:      $port"
echo "filename:  $filename"
echo "configDir: $configdir"
echo "version:   $version"
echo "name:      $name"

# 配置文件路径
configfile=$configdir/$filename
dconfigfile=$dconfigdir/$filename
images=prom/blackbox-exporter

# docker 安装
if ! [ "$(docker images $images:$version -q)" ]; then
  echo "开始安装 $images:$version"
  docker pull $images:$version
  if ! [ "$(docker images $images:$version -q)" ]; then
    echo "拉取 docker 镜像 $images:$version 失败" >&2
    echo '请检查网络或者镜像标签是否异常，然后执行命令以下：'
    echo "  docker pull $images:$version  "
    echo '镜像拉取成功后，再重新执行安装脚本'
    exit 1
  fi
fi

if [ ! -d "$configdir" ]; then
  echo "挂载文件目录不存在，生成目录 $configdir "
  mkdir -p $configdir
  if [ ! -d "$configdir" ]; then
    echo '生成目录失败' >&2
    echo "请检查挂载目录  $configdir "
    exit 1
  fi
fi

if [ ! -f "$configfile" ]; then
  echo "创建配置文件 $configfile"
  touch $configfile 
fi

if [ ! -s "$configfile" ]; then
  echo '正在生成配置文件模板'
  tee $configfile << \EOF
modules:
  http_2xx: # 模块名字
    prober: http # 探针类型
    timeout: 5s
    http:
      valid_http_versions: ["HTTP/1.1", "HTTP/2"]
      valid_status_codes: []  # Defaults to 2xx
      method: GET
      headers:
        Host: vhost.example.com
        Accept-Language: en-US
      no_follow_redirects: false
      fail_if_ssl: false
      fail_if_not_ssl: false
      tls_config:
        insecure_skip_verify: false
      preferred_ip_protocol: "ip4" # defaults to "ip6"
      ip_protocol_fallback: false  # no fallback to "ip6"
  http_post_2xx:
    prober: http
    timeout: 5s
    http:
      method: POST
      headers:
        Content-Type: application/json
      body: '{}'
  http_basic_auth:
    prober: http
    timeout: 5s
    http:
      method: POST
      headers:
        Host: "login.example.com"
      basic_auth:
        username: "username"
        password: "mysecret"
  http_custom_ca:
    prober: http
    http:
      method: GET
      tls_config:
        ca_file: "/certs/my_cert.crt"
  tls_connect_tls:
    prober: tcp
    timeout: 5s
    tcp:
      tls: true
  tcp_connect:
    prober: tcp
    timeout: 5s
  imap_starttls:
    prober: tcp
    timeout: 5s
    tcp:
      query_response:
        - expect: "OK.*STARTTLS"
        - send: ". STARTTLS"
        - expect: "OK"
        - starttls: true
        - send: ". capability"
        - expect: "CAPABILITY IMAP4rev1"
  smtp_starttls:
    prober: tcp
    timeout: 5s
    tcp:
      query_response:
        - expect: "^220 ([^ ]+) ESMTP (.+)$"
        - send: "EHLO prober"
        - expect: "^250-STARTTLS"
        - send: "STARTTLS"
        - expect: "^220"
        - starttls: true
        - send: "EHLO prober"
        - expect: "^250-AUTH"
        - send: "QUIT"
  ssh_banner:
    prober: tcp
    tcp:
      query_response:
      - expect: "^SSH-"
  irc_banner_example:
    prober: tcp
    timeout: 5s
    tcp:
      query_response:
        - send: "NICK prober"
        - send: "USER prober prober prober :prober"
        - expect: "PING :([^ ]+)"
          send: "PONG ${1}"
        - expect: "^:[^ ]+ 001"
  ping:
    prober: icmp
    timeout: 5s
    icmp:
      preferred_ip_protocol: "ip4"

  icmp:
    prober: icmp
    timeout: 5s

  dns_udp:
    prober: dns
    timeout: 5s
    dns:
      query_name: "www.prometheus.io"
      query_type: "A"
      valid_rcodes:
      - NOERROR
      validate_answer_rrs:
        fail_if_matches_regexp:
        - ".*127.0.0.1"
        fail_if_not_matches_regexp:
        - "www.prometheus.io.\t300\tIN\tA\t127.0.0.1"
      validate_authority_rrs:
        fail_if_matches_regexp:
        - ".*127.0.0.1"
      validate_additional_rrs:
        fail_if_matches_regexp:
        - ".*127.0.0.1"
  dns_soa:
    prober: dns
    dns:
      query_name: "prometheus.io"
      query_type: "SOA"
  dns_tcp:
    prober: dns
    dns:
      transport_protocol: "tcp" # defaults to "udp"
      preferred_ip_protocol: "ip4" # defaults to "ip6"
      query_name: "www.prometheus.io"
EOF
  echo '初始化配置文件模板完成，可通过命令查看配置文件内容'
  echo " cat $configfile "
fi

if ! [ "$(docker ps -a -q -f name=$name)" ]; then
  docker run --restart=always -d -p $port:9115 --name $name \
    -v $configdir:$dconfigdir $images:$version \
    --config.file=$dconfigfile
  if ! [ "$(docker ps -q -f name=$name)" ]; then
    echo 'blackbox-exporter docker 启动失败，请检查启动命令' >&2
    echo " docker run --restart=always -d -p $port:9115 --name $name \
    -v $configdir:$dconfigdir $images:$version \
    --config.file=$dconfigfile " >&2
    exit 1
  fi

else
  echo "容器'$name'已经存在，请重新指定'-n'参数，并确保容器名未重复；或者检查'blackbox-exporter'是否已经在运行" >&2
  echo "若确定指定启动容器名为'$name'，请用以下命令检查容器并确认删除，然后重新执行此脚本" >&2
  echo " 检查： docker ps -a -f name=$name "
  echo " 删除： docker  kill $name && docker rm $name "
  exit 1
fi

if ! [ $(systemctl is-enabled docker) = 'enabled' ]; then 
  echo '设置 docker 开机启动' 
  systemctl enable docker.service
  if ! [ $(systemctl is-enabled docker) = 'enabled' ]; then 
    echo '设置 docker 开机启动失败，请尝试执行以下命令' >&2
    echo ' systemctl enable docker.service ' >&2
    exit 1
  fi
fi
echo ' blackbox_exporter 安装启动成功！'
echo " 查看配置文件路径：$configfile "
echo " 查看 server 信息访问 127.0.0.1:$port "