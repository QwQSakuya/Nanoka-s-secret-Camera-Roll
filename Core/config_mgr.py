import os
import sys
import json
from PIL import Image
from Core.logger import logger

def get_root_dir():
    if getattr(sys, 'frozen', False):
        # 如果是打包后的 exe 运行，获取 exe 所在的目录
        return os.path.dirname(sys.executable)
    else:
        # 如果是 python 脚本运行，获取脚本所在目录（根据你的实际层级调整）
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
class ConfigManager:
    """
    全局配置与表情包配置管理器
    """
    def __init__(self):
        # 【修复】：第一时间获取正确的根目录
        self.root_dir = get_root_dir()
        
        self.global_config_path = os.path.join(self.root_dir, "Configs", "global_settings.json")
        self.emotes_dir = os.path.join(self.root_dir, "EmoteConfigs")
        
        os.makedirs(os.path.dirname(self.global_config_path), exist_ok=True)
        os.makedirs(self.emotes_dir, exist_ok=True)
        
        self.global_settings = {}
        self.emotes_configs = []

    def load_global_settings(self) -> dict:
        # 尝试直接读取配置，不再自动生成默认配置，因为打包时会自带 config
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
        
        # 移除自动生成模板的调用，改为直接跳过并给出警告
        if not os.path.exists(self.emotes_dir) or not os.listdir(self.emotes_dir):
            logger.warning("EmoteConfigs 文件夹为空或不存在，请确保打包时附带了表情包配置。")
            return self.emotes_configs

        for folder_name in os.listdir(self.emotes_dir):
            folder_path = os.path.join(self.emotes_dir, folder_name)
            config_path = os.path.join(folder_path, "config.json")
            
            if os.path.isdir(folder_path) and os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        config_data["_folder_path"] = folder_path
                        self.emotes_configs.append(config_data)
                except Exception as e:
                    logger.error(f"加载表情包 {folder_name} 失败: {e}")
                    
        return self.emotes_configs
