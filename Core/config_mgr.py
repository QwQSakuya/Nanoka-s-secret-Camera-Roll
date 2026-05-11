import os
import sys
import json
from PIL import Image
from Core.logger import logger

def get_root_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
class ConfigManager:
    """全局配置与表情包配置管理器"""
    def __init__(self):
        self.root_dir = get_root_dir()
        
        self.global_config_path = os.path.join(self.root_dir, "Configs", "global_settings.json")
        self.emotes_dir = os.path.join(self.root_dir, "EmoteConfigs")
        
        os.makedirs(os.path.dirname(self.global_config_path), exist_ok=True)
        os.makedirs(self.emotes_dir, exist_ok=True)
        
        self.global_settings = {}
        self.emotes_configs = []

    def load_global_settings(self) -> dict:
        if os.path.exists(self.global_config_path):
            try:
                with open(self.global_config_path, 'r', encoding='utf-8') as f:
                    self.global_settings = json.load(f)
            except Exception as e:
                logger.warning(f"读取全局设置失败: {e}")
                
        return self.global_settings

    def save_global_settings(self, settings: dict):
        try:
            with open(self.global_config_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            self.global_settings = settings
        except Exception as e:
            logger.error(f"保存全局设置失败: {e}")

    def load_all_emotes(self) -> list:
        self.emotes_configs = []

        if not os.path.exists(self.emotes_dir):
            logger.warning(f"EmoteConfigs 目录不存在: {self.emotes_dir}")
            return self.emotes_configs

        try:
            entries = os.listdir(self.emotes_dir)
        except PermissionError:
            logger.exception(f"无权限读取 EmoteConfigs 目录: {self.emotes_dir}")
            return self.emotes_configs

        if not entries:
            logger.warning("EmoteConfigs 文件夹为空，请确保打包时附带了表情包配置。")
            return self.emotes_configs

        loaded_count = 0
        for folder_name in entries:
            folder_path = os.path.join(self.emotes_dir, folder_name)
            config_path = os.path.join(folder_path, "config.json")

            if os.path.isdir(folder_path) and os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        config_data["_folder_path"] = folder_path
                        self.emotes_configs.append(config_data)
                        loaded_count += 1
                except json.JSONDecodeError:
                    logger.exception(f"表情包配置 JSON 解析失败: {folder_name}")
                except Exception:
                    logger.exception(f"加载表情包 {folder_name} 时发生未知异常")

        logger.info(f"表情包加载完成: 共 {loaded_count}/{len(entries)} 个目录成功")
        return self.emotes_configs
