# model-hardware-standard

这个包提供与通信方式无关的 Endpoint 发现流程，以及 TCP 和 VISA Transport。

## VISA 自动发现

```python
from src.server.discover.discover import Discovery
from src.transport.visa.visa import VisaTransportModule

result = Discovery([VisaTransportModule()]).discover()

for endpoint in result.endpoints:
    print(endpoint.resource)
```

`VisaTransportModule()` 每次被调用时会执行一次有限的发现：

1. 询问 PyVISA-py (`@py`) 能报告哪些资源；
2. 根据本机私有 IPv4 网卡和掩码得到局域网；
3. 并发检查 VXI-11 portmapper 的 TCP 111 端口；
4. 对可能的主机生成 `TCPIP0::<host>::inst0::INSTR`；
5. 由通用 `Discovery` 对每个候选执行 `open()` 和 `close()`。

这不是设备身份识别。发现阶段不会发送 `*IDN?`，也不会读取、写入、注册设备。Endpoint 只表示该 VISA 地址在本次扫描中可以建立连接。

### 配置扫描网段

如果不希望读取本机网卡，或者希望使用指定网段，可以传入 CIDR：

```python
module = VisaTransportModule(
    subnets=("192.168.3.0/24",),
)
result = Discovery([module]).discover()
```

只使用 PyVISA-py 自动枚举和已知资源时，可以关闭网段扫描：

```python
module = VisaTransportModule(
    resources=("TCPIP0::192.168.3.91::inst0::INSTR",),
    auto_discover_local_networks=False,
)
```

扫描有主机数量、候选数量、并发数和连接超时限制。默认只扫描处于启用状态的私有或本地链路 IPv4 网卡；超过主机上限的大网段会跳过，如果没有可安全扫描的网段，结果中会给出错误并提示配置更小的 CIDR。程序不会扫描任意 TCP 端口，也不会把 TCP 5025 当作 VISA 的固定端口。原始 `TCPIP::<host>::<port>::SOCKET` 地址仍需显式提供，HiSLIP 和 USB 资源由 PyVISA-py 的资源枚举负责。

PyVISA 会在同一进程中复用 ResourceManager，因此发现模块只关闭自己打开的仪器 Resource，不会关闭共享 ResourceManager，避免影响其他正在使用的仪器连接。

`discover()` 是一次性的同步调用。Transport 模块不会自动启动线程、定时器或监听插拔事件；上层决定何时调用它。
