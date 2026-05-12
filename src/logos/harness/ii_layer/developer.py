"""开发者运行时开关（可变状态，挂在 AppPorts 上供 HTTP 层改写）。"""


class DeveloperToggles:
    """与 :class:`~logos.ports.settings.AppSettings` 分离：配置提供初值，此处可 GUI 实时切换。"""

    __slots__ = ("prompt_echo",)

    def __init__(self, *, prompt_echo: bool) -> None:
        self.prompt_echo = prompt_echo
