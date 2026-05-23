"""支撑层 / Platform layer（``logos.platform``）：I&I、S&G、Obs、Config。"""



from logos.platform.config import load_app_settings, load_merged_config_dict

from logos.platform.obs import configure_logging



__all__ = [

    "configure_logging",

    "load_app_settings",

    "load_merged_config_dict",

]



