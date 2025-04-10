#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import sys

# Make sure parent directory is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import load_settings, EmailConfig
from notifiers.email_notifier import EmailNotifier


def setup_logging():
    """配置日志输出"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )


def send_test_email(config_path='config/settings.yaml'):
    """
    发送测试邮件
    
    Args:
        config_path: 配置文件路径
    
    Returns:
        发送是否成功
    """
    logger = logging.getLogger(__name__)
    
    try:
        # 从配置文件加载设置
        logger.info(f"从 {config_path} 加载配置")
        config = load_settings(config_path)
        email_config = config.email
        
        # 显示有效的邮件配置
        logger.info(f"SMTP 服务器: {email_config.smtp_server}:{email_config.smtp_port}")
        logger.info(f"发件人: {email_config.sender}")
        logger.info(f"收件人: {', '.join(email_config.recipients)}")
        logger.info(f"使用 TLS: {email_config.use_tls}")
        
        # 初始化邮件发送器
        logger.info("初始化 Email 发送器")
        notifier = EmailNotifier(email_config)
        
        # 发送测试邮件
        subject = "流量监控系统测试邮件"
        message = "这是一封来自流量监控系统的测试邮件，用于验证邮件发送功能是否正常工作。"
        
        logger.info(f"正在发送测试邮件: '{subject}'")
        result = notifier.notify(
            subject=subject,
            message=message,
            level="info"
        )
        
        if result:
            logger.info("✓ 邮件发送成功!")
            return True
        else:
            logger.error("✗ 邮件发送失败")
            return False
            
    except Exception as e:
        logger.error(f"发生错误: {e}")
        return False


def main():
    """主函数入口"""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("启动邮件发送测试程序")
    
    # 确定配置文件路径
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = 'config/settings.yaml'
    
    # 发送测试邮件
    success = send_test_email(config_path)
    
    # 返回适当的退出码
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main()) 