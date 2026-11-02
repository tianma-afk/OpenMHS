import logging
from model_hardware_standard.registry import Registry
from model_hardware_standard.visa_discovery import VISADiscovery
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


class DeviceManager:
    def __init__(self, discovery: VISADiscovery, registry: Registry):
        self.discovery = discovery
        self.registry = registry
        self.interval = 5  # seconds
        self.scheduler = BackgroundScheduler()

    def refresh(self):
        try:
            devices = self.discovery.discover()
        except Exception:
            logger.exception("本轮设备发现失败，保留已有设备记录，等待下次重试")
            return
        self.registry.register(devices)
        # print(f"Discovered and registered {len(devices)} devices.")
        # print(f"Current devices in registry: {[device.__dict__ for device in self.registry.device_repo]}")

    def start(self):
        self.scheduler.add_job(
            self.refresh,
            "interval",
            seconds=self.interval,
            max_instances=1,
            id="device_refresh" 
        )
        self.scheduler.start()

    def pause(self):
        self.scheduler.pause()

    def resume(self):
        self.scheduler.resume()

    def stop(self):
        self.scheduler.shutdown()

    def set_interval(self, interval: int):
        self.interval = interval
        job = self.scheduler.get_job("device_refresh")
        if job:
            self.scheduler.reschedule_job(
                "device_refresh",        
                trigger="interval",
                seconds=self.interval
            )

    def get_devices(self):
        return self.registry.device_repo

_manager: DeviceManager | None = None

def set_device_manager(mgr: DeviceManager):   # lifespan 里调用
    global _manager
    _manager = mgr

def get_device_manager() -> DeviceManager:
    if _manager is None:
        raise RuntimeError("DeviceManager not initialized")
    return _manager