# -*- coding: utf-8 -*-
from pages.base_page import BasePage
from pages.login_page import LoginPage
from pages.status_page import StatusPage
from pages.wifi_page import WifiPage
from pages.wan_page import WanPage
from pages.lan_page import LanPage
from pages.system_page import SystemPage
from pages.upgrade_page import UpgradePage
from pages.nav_bar import NavBar

__all__ = [
    "BasePage", "LoginPage", "StatusPage", "WifiPage", "WanPage",
    "LanPage", "SystemPage", "UpgradePage", "NavBar",
]
