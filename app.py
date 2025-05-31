#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPS位置管理系统
轻量化单体应用架构
"""

from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import sqlite3
import json
import math
import gzip
import base64
import os
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import shutil
import redis
from functools import wraps
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gps-system-secret-key-2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gps_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 数据库初始化
db = SQLAlchemy(app)

# Redis连接（如果可用）
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    redis_client.ping()
    REDIS_AVAILABLE = True
except:
    REDIS_AVAILABLE = False
    logger.warning("Redis不可用，使用内存缓存")

# ==================== 数据库模型 ====================

class Admin(db.Model):
    """管理员表"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

class VehicleOwner(db.Model):
    """车主用户表"""
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    owner_name = db.Column(db.String(100))
    id_card = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)

class VehicleModel(db.Model):
    """车型表"""
    id = db.Column(db.Integer, primary_key=True)
    model_code = db.Column(db.String(50), unique=True, nullable=False)
    model_name = db.Column(db.String(100), nullable=False)
    manufacturer = db.Column(db.String(50))
    year_range = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)

class Software(db.Model):
    """软件表"""
    id = db.Column(db.Integer, primary_key=True)
    app_package = db.Column(db.String(100), unique=True, nullable=False)
    app_name = db.Column(db.String(100), nullable=False)
    app_icon_url = db.Column(db.String(255))
    version = db.Column(db.String(20))
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Device(db.Model):
    """设备表"""
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100), unique=True, nullable=False)
    device_name = db.Column(db.String(100))
    vehicle_model_id = db.Column(db.Integer, db.ForeignKey('vehicle_model.id'))
    owner_id = db.Column(db.Integer, db.ForeignKey('vehicle_owner.id'))
    vehicle_plate = db.Column(db.String(20))
    vehicle_vin = db.Column(db.String(50))
    status = db.Column(db.String(20), default='offline')  # online, offline, disabled
    last_seen = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关系
    owner = db.relationship('VehicleOwner', backref='devices')
    vehicle_model = db.relationship('VehicleModel', backref='devices')

class DeviceAppPermission(db.Model):
    """设备-软件授权表"""
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100), db.ForeignKey('device.device_id'))
    software_id = db.Column(db.Integer, db.ForeignKey('software.id'))
    is_authorized = db.Column(db.Boolean, default=True)
    authorized_by = db.Column(db.String(50))
    authorized_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    
    # 关系
    software = db.relationship('Software', backref='permissions')

class LocationCurrent(db.Model):
    """当前位置表（每设备最新10条）"""
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    altitude = db.Column(db.Float)
    accuracy = db.Column(db.Float)
    speed = db.Column(db.Float)
    heading = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.Index('idx_device_time', 'device_id', 'timestamp'),)

class ElectronicFence(db.Model):
    """电子围栏表"""
    id = db.Column(db.Integer, primary_key=True)
    fence_name = db.Column(db.String(100), nullable=False)
    fence_type = db.Column(db.String(20), nullable=False)  # circle, polygon, region
    coordinates = db.Column(db.Text, nullable=False)  # JSON格式存储坐标
    radius = db.Column(db.Float)  # 圆形围栏半径
    device_ids = db.Column(db.Text)  # JSON格式存储适用设备ID
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SystemConfig(db.Model):
    """系统配置表"""
    id = db.Column(db.Integer, primary_key=True)
    config_key = db.Column(db.String(50), unique=True, nullable=False)
    config_value = db.Column(db.Text)
    description = db.Column(db.String(200))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==================== 工具函数 ====================

def compress_gps_data(locations):
    """GPS数据压缩"""
    if not locations:
        return ""
    
    # 简化坐标精度到6位小数
    simplified = []
    for loc in locations:
        simplified.append({
            'lat': round(loc['latitude'], 6),
            'lng': round(loc['longitude'], 6),
            'time': int(loc['timestamp'].timestamp())
        })
    
    # JSON压缩
    json_str = json.dumps(simplified, separators=(',', ':'))
    compressed = gzip.compress(json_str.encode('utf-8'))
    return base64.b64encode(compressed).decode('utf-8')

def decompress_gps_data(compressed_data):
    """GPS数据解压"""
    if not compressed_data:
        return []
    
    try:
        compressed = base64.b64decode(compressed_data.encode('utf-8'))
        json_str = gzip.decompress(compressed).decode('utf-8')
        return json.loads(json_str)
    except:
        return []

def calculate_distance(lat1, lon1, lat2, lon2):
    """计算两点间距离（米）"""
    R = 6371000  # 地球半径（米）
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lon/2) * math.sin(delta_lon/2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def is_same_location(lat1, lon1, lat2, lon2, threshold=50):
    """判断是否为相同位置（防抖）"""
    distance = calculate_distance(lat1, lon1, lat2, lon2)
    return distance < threshold

def calculate_speed(lat1, lon1, time1, lat2, lon2, time2):
    """计算速度（km/h）"""
    distance = calculate_distance(lat1, lon1, lat2, lon2)
    time_diff = (time2 - time1).total_seconds()
    if time_diff <= 0:
        return 0
    speed_ms = distance / time_diff
    return speed_ms * 3.6  # 转换为km/h

def check_storage_usage():
    """检查存储使用情况"""
    total, used, free = shutil.disk_usage('/')
    usage_percent = (used / total) * 100
    free_gb = free / (1024**3)
    
    return {
        'usage_percent': usage_percent,
        'free_gb': free_gb,
        'total_gb': total / (1024**3),
        'used_gb': used / (1024**3)
    }

def send_storage_alert():
    """发送存储不足邮件"""
    try:
        # 获取邮件配置
        smtp_config = get_system_config('smtp_config', {})
        if not smtp_config:
            logger.error("邮件配置不存在")
            return False
        
        msg = MimeMultipart()
        msg['From'] = smtp_config.get('from_email')
        msg['To'] = smtp_config.get('to_email')
        msg['Subject'] = "服务器容量不足警告"
        
        body = "服务器容量不足，请及时处理"
        msg.attach(MimeText(body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP(smtp_config.get('smtp_host'), smtp_config.get('smtp_port'))
        server.starttls()
        server.login(smtp_config.get('username'), smtp_config.get('password'))
        server.send_message(msg)
        server.quit()
        
        logger.info("存储警告邮件发送成功")
        return True
    except Exception as e:
        logger.error(f"发送邮件失败: {e}")
        return False

def get_system_config(key, default=None):
    """获取系统配置"""
    config = SystemConfig.query.filter_by(config_key=key).first()
    if config:
        try:
            return json.loads(config.config_value)
        except:
            return config.config_value
    return default

def set_system_config(key, value, description=""):
    """设置系统配置"""
    config = SystemConfig.query.filter_by(config_key=key).first()
    if config:
        config.config_value = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        config.updated_at = datetime.utcnow()
    else:
        config = SystemConfig(
            config_key=key,
            config_value=json.dumps(value) if isinstance(value, (dict, list)) else str(value),
            description=description
        )
        db.session.add(config)
    db.session.commit()

# ==================== 认证装饰器 ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== 路由定义 ====================

@app.route('/')
def index():
    """首页重定向到管理后台"""
    return redirect(url_for('admin_dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """管理员登录"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            session['admin_id'] = admin.id
            session['admin_username'] = admin.username
            admin.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('admin_dashboard'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """退出登录"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """管理后台首页"""
    # 统计数据
    stats = {
        'total_devices': Device.query.count(),
        'online_devices': Device.query.filter_by(status='online').count(),
        'total_owners': VehicleOwner.query.count(),
        'total_software': Software.query.filter_by(is_active=True).count(),
        'storage_info': check_storage_usage()
    }
    
    # 最近位置更新
    recent_locations = db.session.query(LocationCurrent).order_by(LocationCurrent.timestamp.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html', stats=stats, recent_locations=recent_locations)

# ==================== GPS数据API ====================

@app.route('/api/gps/upload', methods=['POST'])
def upload_gps_data():
    """设备上传GPS数据"""
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        locations = data.get('locations', [])
        
        if not device_id or not locations:
            return jsonify({'error': '缺少必要参数'}), 400
        
        # 验证设备是否存在
        device = Device.query.filter_by(device_id=device_id).first()
        if not device:
            return jsonify({'error': '设备不存在'}), 404
        
        # 处理位置数据
        processed_count = 0
        for loc_data in locations:
            lat = loc_data.get('latitude')
            lng = loc_data.get('longitude')
            timestamp = datetime.fromisoformat(loc_data.get('timestamp', datetime.utcnow().isoformat()))
            
            if not lat or not lng:
                continue
            
            # 检查是否为重复位置（防抖）
            last_location = LocationCurrent.query.filter_by(device_id=device_id).order_by(LocationCurrent.timestamp.desc()).first()
            if last_location and is_same_location(lat, lng, last_location.latitude, last_location.longitude):
                continue
            
            # 保存位置数据
            location = LocationCurrent(
                device_id=device_id,
                latitude=lat,
                longitude=lng,
                altitude=loc_data.get('altitude'),
                accuracy=loc_data.get('accuracy'),
                speed=loc_data.get('speed'),
                heading=loc_data.get('heading'),
                timestamp=timestamp
            )
            db.session.add(location)
            processed_count += 1
            
            # 保持每设备最多10条记录
            device_locations = LocationCurrent.query.filter_by(device_id=device_id).order_by(LocationCurrent.timestamp.desc()).all()
            if len(device_locations) >= 10:
                for old_loc in device_locations[9:]:
                    db.session.delete(old_loc)
        
        # 更新设备状态
        device.status = 'online'
        device.last_seen = datetime.utcnow()
        
        db.session.commit()
        
        # 检查存储使用情况
        storage_info = check_storage_usage()
        if storage_info['usage_percent'] > 80:
            send_storage_alert()
        
        return jsonify({
            'status': 'success',
            'processed_count': processed_count,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"GPS数据上传失败: {e}")
        return jsonify({'error': '服务器内部错误'}), 500

@app.route('/api/devices/<device_id>/location')
def get_device_location(device_id):
    """获取设备当前位置"""
    try:
        location = LocationCurrent.query.filter_by(device_id=device_id).order_by(LocationCurrent.timestamp.desc()).first()
        if not location:
            return jsonify({'error': '设备位置不存在'}), 404
        
        return jsonify({
            'device_id': device_id,
            'latitude': location.latitude,
            'longitude': location.longitude,
            'altitude': location.altitude,
            'accuracy': location.accuracy,
            'speed': location.speed,
            'heading': location.heading,
            'timestamp': location.timestamp.isoformat()
        })
    except Exception as e:
        logger.error(f"获取设备位置失败: {e}")
        return jsonify({'error': '服务器内部错误'}), 500

@app.route('/api/devices/<device_id>/history')
def get_device_history(device_id):
    """获取设备历史轨迹"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = LocationCurrent.query.filter_by(device_id=device_id)
        
        if start_date:
            query = query.filter(LocationCurrent.timestamp >= datetime.fromisoformat(start_date))
        if end_date:
            query = query.filter(LocationCurrent.timestamp <= datetime.fromisoformat(end_date))
        
        locations = query.order_by(LocationCurrent.timestamp.asc()).all()
        
        history = []
        for loc in locations:
            history.append({
                'latitude': loc.latitude,
                'longitude': loc.longitude,
                'altitude': loc.altitude,
                'speed': loc.speed,
                'timestamp': loc.timestamp.isoformat()
            })
        
        return jsonify({
            'device_id': device_id,
            'history': history,
            'total_points': len(history)
        })
    except Exception as e:
        logger.error(f"获取历史轨迹失败: {e}")
        return jsonify({'error': '服务器内部错误'}), 500

# ==================== 设备管理API ====================

@app.route('/api/devices')
@login_required
def get_devices():
    """获取设备列表"""
    try:
        devices = db.session.query(Device, VehicleOwner, VehicleModel).outerjoin(VehicleOwner).outerjoin(VehicleModel).all()
        
        device_list = []
        for device, owner, model in devices:
            # 获取最新位置
            latest_location = LocationCurrent.query.filter_by(device_id=device.device_id).order_by(LocationCurrent.timestamp.desc()).first()
            
            device_info = {
                'device_id': device.device_id,
                'device_name': device.device_name,
                'status': device.status,
                'last_seen': device.last_seen.isoformat() if device.last_seen else None,
                'vehicle_plate': device.vehicle_plate,
                'owner': {
                    'phone_number': owner.phone_number if owner else None,
                    'owner_name': owner.owner_name if owner else None
                } if owner else None,
                'vehicle_model': {
                    'model_name': model.model_name if model else None,
                    'manufacturer': model.manufacturer if model else None
                } if model else None,
                'latest_location': {
                    'latitude': latest_location.latitude,
                    'longitude': latest_location.longitude,
                    'timestamp': latest_location.timestamp.isoformat()
                } if latest_location else None
            }
            device_list.append(device_info)
        
        return jsonify({
            'devices': device_list,
            'total': len(device_list)
        })
    except Exception as e:
        logger.error(f"获取设备列表失败: {e}")
        return jsonify({'error': '服务器内部错误'}), 500

# ==================== 初始化函数 ====================

def init_database():
    """初始化数据库"""
    with app.app_context():
        db.create_all()
        
        # 创建默认管理员
        admin = Admin.query.filter_by(username='admin').first()
        if not admin:
            admin = Admin(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                email='admin@example.com'
            )
            db.session.add(admin)
        
        # 创建默认车型
        if not VehicleModel.query.first():
            models = [
                VehicleModel(model_code='NISSAN_X_TRAIL', model_name='奇骏', manufacturer='日产'),
                VehicleModel(model_code='NISSAN_SYLPHY', model_name='轩逸', manufacturer='日产'),
                VehicleModel(model_code='NISSAN_TEANA', model_name='天籁', manufacturer='日产'),
            ]
            for model in models:
                db.session.add(model)
        
        # 创建默认软件
        if not Software.query.first():
            software_list = [
                Software(app_package='com.amap.android.location', app_name='高德地图', category='导航'),
                Software(app_package='com.tencent.mm', app_name='微信', category='社交'),
                Software(app_package='com.netease.cloudmusic', app_name='网易云音乐', category='音乐'),
            ]
            for software in software_list:
                db.session.add(software)
        
        # 初始化系统配置
        if not SystemConfig.query.filter_by(config_key='speed_limit_enabled').first():
            configs = [
                SystemConfig(config_key='speed_limit_enabled', config_value='true', description='是否启用超速检测'),
                SystemConfig(config_key='dynamic_speed_limit', config_value='true', description='是否启用动态限速'),
                SystemConfig(config_key='default_speed_limit', config_value='60', description='默认限速(km/h)'),
                SystemConfig(config_key='storage_alert_threshold', config_value='80', description='存储警告阈值(%)'),
            ]
            for config in configs:
                db.session.add(config)
        
        db.session.commit()
        logger.info("数据库初始化完成")

if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', port=5000, debug=False) 