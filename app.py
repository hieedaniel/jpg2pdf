#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JPG2PDF Web应用 - Flask后端
支持上传图片、排序、生成PDF
"""

import os
import re
import uuid
import time
import magic
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import img2pdf
from PIL import Image

app = Flask(__name__)

# 配置
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
PDF_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'pdfs')
THUMBNAIL_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'thumbnails')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'bmp', 'gif', 'webp'}
# 允许的 MIME 类型白名单
ALLOWED_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/gif',
    'image/bmp', 'image/webp', 'image/x-ms-bmp'
}
# 文件魔数（Magic Number）白名单 - 用于验证文件真实类型
FILE_SIGNATURES = {
    b'\xff\xd8\xff': 'jpeg',           # JPEG
    b'\x89PNG\r\n\x1a\n': 'png',       # PNG
    b'GIF87a': 'gif',                  # GIF87a
    b'GIF89a': 'gif',                  # GIF89a
    b'BM': 'bmp',                      # BMP
    b'RIFF': 'webp',                   # WebP (RIFF...WEBP)
}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB最大上传
MAX_FILES_PER_SESSION = 50            # 每个会话最大文件数
THUMBNAIL_SIZE = (120, 120)            # 缩略图尺寸（移动端优化）

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PDF_FOLDER'] = PDF_FOLDER
app.config['THUMBNAIL_FOLDER'] = THUMBNAIL_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 确保目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def verify_file_signature(file_data):
    """
    验证文件魔数（Magic Number）
    返回检测到的文件类型，如果不在白名单中返回 None
    """
    for signature, file_type in FILE_SIGNATURES.items():
        if file_data.startswith(signature):
            return file_type
    # WebP 特殊处理：RIFF 头 + 文件大小 + WEBP
    if file_data.startswith(b'RIFF') and file_data[8:12] == b'WEBP':
        return 'webp'
    return None


def verify_mime_type(file_data):
    """
    使用 python-magic 验证文件 MIME 类型
    返回 MIME 类型字符串
    """
    try:
        mime = magic.from_buffer(file_data, mime=True)
        return mime
    except Exception:
        return None


def is_safe_filename(filename):
    """
    检查文件名是否安全
    防止路径遍历和特殊字符攻击
    """
    # 移除路径分隔符和其他危险字符
    safe_name = secure_filename(filename)
    if not safe_name:
        return False
    # 检查是否包含路径遍历字符
    if '..' in filename or '/' in filename or '\\' in filename:
        return False
    # 检查是否为隐藏文件
    if filename.startswith('.'):
        return False
    return True


def is_safe_file_id(file_id):
    """
    检查文件 ID 是否安全
    防止路径遍历攻击
    """
    # UUID 格式 + 扩展名
    pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\.(jpg|jpeg|png|bmp|gif|webp)$'
    return bool(re.match(pattern, file_id, re.IGNORECASE))


def validate_image_file(file_path):
    """
    使用 PIL 验证图片文件是否有效
    返回 (是否有效, 图片尺寸)
    """
    try:
        with Image.open(file_path) as img:
            img.verify()  # 验证文件完整性
        # 重新打开获取尺寸（verify 后需要重新打开）
        with Image.open(file_path) as img:
            return True, img.size
    except Exception:
        return False, (0, 0)


def create_thumbnail(source_path, thumbnail_path, size=THUMBNAIL_SIZE):
    """
    创建缩略图（移动端优化）
    使用高质量缩放，保持宽高比
    """
    try:
        with Image.open(source_path) as img:
            # 转换为 RGB 模式（处理 PNG 透明通道等）
            if img.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # 创建缩略图（使用 BILINEAR 快速缩放）
            img.thumbnail(size, Image.Resampling.BILINEAR)
            # 保存为渐进式JPEG，低质量优化移动端加载
            img.save(thumbnail_path, 'JPEG', quality=60, optimize=True, progressive=True)
            return True
    except Exception:
        return False


def prepare_images_for_pdf(image_paths, output_folder):
    """
    准备用于PDF的图片，统一宽度对齐
    以第一张图片的宽度为标准，其他图片适配
    返回处理后的图片路径列表
    """
    if not image_paths:
        return image_paths

    # 获取第一张图片的宽度作为标准
    target_width = None
    try:
        with Image.open(image_paths[0]) as img:
            target_width = img.size[0]
    except Exception:
        return image_paths

    if not target_width:
        return image_paths

    # PDF 页面宽度限制（设一个合理的上限）
    PDF_MAX_WIDTH = 1200
    target_width = min(target_width, PDF_MAX_WIDTH)

    processed_paths = []

    for path in image_paths:
        try:
            with Image.open(path) as img:
                orig_width, orig_height = img.size

                # 转换为 RGB 模式
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # 计算缩放后的尺寸，保持宽高比（统一处理所有图片）
                scale_ratio = target_width / orig_width
                new_height = int(orig_height * scale_ratio)

                # 高质量缩放
                resized = img.resize((target_width, new_height), Image.Resampling.LANCZOS)

                # 保存处理后的图片
                processed_name = f"processed_{uuid.uuid4()}.jpg"
                processed_path = os.path.join(output_folder, processed_name)
                resized.save(processed_path, 'JPEG', quality=95, optimize=True)
                processed_paths.append(processed_path)
        except Exception as e:
            # 如果处理失败，尝试直接使用原图
            processed_paths.append(path)

    return processed_paths


def cleanup_old_files(folder, max_age_hours=24):
    """清理超过指定时间的旧文件"""
    now = time.time()
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        if os.path.isfile(filepath):
            file_age = now - os.path.getmtime(filepath)
            if file_age > max_age_hours * 3600:
                try:
                    os.remove(filepath)
                except:
                    pass


@app.route('/')
def index():
    """主页面"""
    # 启动时清理旧文件
    cleanup_old_files(UPLOAD_FOLDER)
    cleanup_old_files(PDF_FOLDER)
    cleanup_old_files(THUMBNAIL_FOLDER)
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    """上传图片"""
    files = request.files.getlist('files')

    if not files:
        return jsonify({'error': '没有选择文件'}), 400

    uploaded_files = []
    session_id = request.form.get('session_id') or str(uuid.uuid4())

    # 验证 session_id 格式，防止路径遍历
    try:
        uuid.UUID(session_id)
    except ValueError:
        return jsonify({'error': '无效的会话ID'}), 400

    # 创建会话目录
    session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    thumbnail_folder = os.path.join(app.config['THUMBNAIL_FOLDER'], session_id)
    os.makedirs(session_folder, exist_ok=True)
    os.makedirs(thumbnail_folder, exist_ok=True)

    # 检查会话文件数量限制
    existing_files = len([f for f in os.listdir(session_folder) if os.path.isfile(os.path.join(session_folder, f))])
    if existing_files + len(files) > MAX_FILES_PER_SESSION:
        return jsonify({'error': f'超过最大文件数限制（{MAX_FILES_PER_SESSION}）'}), 400

    for file in files:
        # 第一层：基本检查
        if not file or not file.filename:
            continue

        # 第二层：扩展名检查
        if not allowed_file(file.filename):
            continue

        # 第三层：文件名安全检查
        if not is_safe_filename(file.filename):
            continue

        # 读取文件内容进行深度验证
        file_data = file.read()
        file.seek(0)  # 重置文件指针

        # 第四层：文件大小二次检查
        if len(file_data) > MAX_CONTENT_LENGTH:
            continue

        # 第五层：文件魔数验证 - 防止伪造扩展名
        detected_type = verify_file_signature(file_data)
        if not detected_type:
            continue

        # 第六层：MIME 类型验证
        mime_type = verify_mime_type(file_data)
        if mime_type not in ALLOWED_MIME_TYPES:
            continue

        # 第七层：扩展名与实际类型匹配检查
        ext = file.filename.rsplit('.', 1)[1].lower()
        ext_type_map = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png', 'gif': 'gif', 'bmp': 'bmp', 'webp': 'webp'}
        expected_type = ext_type_map.get(ext)
        if detected_type != expected_type:
            continue

        # 使用UUID作为文件名，保留原始扩展名
        unique_name = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(session_folder, unique_name)

        # 保存文件
        with open(filepath, 'wb') as f:
            f.write(file_data)

        # 第八层：PIL 验证图片有效性
        is_valid, dimensions = validate_image_file(filepath)
        if not is_valid:
            # 验证失败，删除文件
            try:
                os.remove(filepath)
            except:
                pass
            continue

        # 创建缩略图
        thumbnail_name = f"{unique_name.rsplit('.', 1)[0]}.jpg"
        thumbnail_path = os.path.join(thumbnail_folder, thumbnail_name)
        create_thumbnail(filepath, thumbnail_path)

        uploaded_files.append({
            'id': unique_name,
            'filename': secure_filename(file.filename),
            'path': f'/static/uploads/{session_id}/{unique_name}',
            'thumbnail': f'/static/thumbnails/{session_id}/{thumbnail_name}',
            'width': dimensions[0],
            'height': dimensions[1]
        })

    return jsonify({
        'success': True,
        'session_id': session_id,
        'files': uploaded_files
    })


@app.route('/delete', methods=['POST'])
def delete():
    """删除单个图片"""
    data = request.get_json()
    session_id = data.get('session_id')
    file_id = data.get('file_id')

    if not session_id or not file_id:
        return jsonify({'error': '缺少参数'}), 400

    # 验证 session_id 格式
    try:
        uuid.UUID(session_id)
    except ValueError:
        return jsonify({'error': '无效的会话ID'}), 400

    # 验证文件 ID 格式，防止路径遍历
    if not is_safe_file_id(file_id):
        return jsonify({'error': '无效的文件ID'}), 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], session_id, file_id)
    thumbnail_name = f"{file_id.rsplit('.', 1)[0]}.jpg"
    thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], session_id, thumbnail_name)

    # 额外验证：确保路径在预期目录内
    real_path = os.path.realpath(filepath)
    if not real_path.startswith(os.path.realpath(app.config['UPLOAD_FOLDER'])):
        return jsonify({'error': '非法路径'}), 400

    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            # 同时删除缩略图
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
            return jsonify({'success': True})
        except:
            return jsonify({'error': '删除失败'}), 500

    return jsonify({'error': '文件不存在'}), 404


@app.route('/clear', methods=['POST'])
def clear():
    """清空会话的所有图片"""
    data = request.get_json()
    session_id = data.get('session_id')

    if not session_id:
        return jsonify({'error': '缺少session_id'}), 400

    # 验证 session_id 格式
    try:
        uuid.UUID(session_id)
    except ValueError:
        return jsonify({'error': '无效的会话ID'}), 400

    session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    thumbnail_folder = os.path.join(app.config['THUMBNAIL_FOLDER'], session_id)

    # 额外验证：确保路径在预期目录内
    real_path = os.path.realpath(session_folder)
    if not real_path.startswith(os.path.realpath(app.config['UPLOAD_FOLDER'])):
        return jsonify({'error': '非法路径'}), 400

    if os.path.exists(session_folder):
        try:
            # 递归删除所有内容（包括 processed 子目录）
            for filename in os.listdir(session_folder):
                filepath = os.path.join(session_folder, filename)
                if os.path.isfile(filepath):
                    os.remove(filepath)
                elif os.path.isdir(filepath):
                    # 删除子目录（如 processed）
                    for subfile in os.listdir(filepath):
                        subpath = os.path.join(filepath, subfile)
                        if os.path.isfile(subpath):
                            os.remove(subpath)
                    try:
                        os.rmdir(filepath)
                    except:
                        pass
            # 同时清空缩略图目录
            if os.path.exists(thumbnail_folder):
                for filename in os.listdir(thumbnail_folder):
                    filepath = os.path.join(thumbnail_folder, filename)
                    if os.path.isfile(filepath):
                        os.remove(filepath)
            return jsonify({'success': True})
        except:
            return jsonify({'error': '清空失败'}), 500

    return jsonify({'success': True})


@app.route('/generate', methods=['POST'])
def generate():
    """生成PDF"""
    data = request.get_json()
    session_id = data.get('session_id')
    file_order = data.get('file_order', [])  # 图片ID排序列表

    if not session_id or not file_order:
        return jsonify({'error': '缺少参数'}), 400

    # 验证 session_id 格式
    try:
        uuid.UUID(session_id)
    except ValueError:
        return jsonify({'error': '无效的会话ID'}), 400

    session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)

    # 额外验证：确保路径在预期目录内
    real_session_path = os.path.realpath(session_folder)
    if not real_session_path.startswith(os.path.realpath(app.config['UPLOAD_FOLDER'])):
        return jsonify({'error': '非法路径'}), 400

    # 检查所有文件是否存在并验证安全性
    image_paths = []
    for file_id in file_order:
        # 验证文件 ID 格式
        if not is_safe_file_id(file_id):
            return jsonify({'error': f'无效的文件ID: {file_id}'}), 400

        filepath = os.path.join(session_folder, file_id)

        # 验证路径在预期目录内
        real_file_path = os.path.realpath(filepath)
        if not real_file_path.startswith(real_session_path):
            return jsonify({'error': '非法路径'}), 400

        if os.path.exists(filepath):
            image_paths.append(filepath)
        else:
            return jsonify({'error': f'文件不存在: {file_id}'}), 404

    if not image_paths:
        return jsonify({'error': '没有图片'}), 400

    # 创建临时处理目录
    processed_folder = os.path.join(session_folder, 'processed')
    os.makedirs(processed_folder, exist_ok=True)

    # 准备图片：统一宽度对齐
    processed_paths = prepare_images_for_pdf(image_paths, processed_folder)

    # 生成PDF
    pdf_filename = f"{session_id}.pdf"
    pdf_path = os.path.join(app.config['PDF_FOLDER'], pdf_filename)

    try:
        with open(pdf_path, 'wb') as f:
            # 图片已统一宽度，直接转换即可
            # img2pdf 会自动为每张图片创建对应尺寸的页面
            f.write(img2pdf.convert(processed_paths))

        # 清理处理后的临时图片
        for path in processed_paths:
            if path.startswith(processed_folder):
                try:
                    os.remove(path)
                except:
                    pass
        try:
            os.rmdir(processed_folder)
        except:
            pass

    except Exception as e:
        return jsonify({'error': f'生成PDF失败: {str(e)}'}), 500

    return jsonify({
        'success': True,
        'pdf_url': f'/download/{pdf_filename}'
    })


@app.route('/download/<filename>')
def download(filename):
    """下载PDF"""
    # 验证文件名格式
    pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\.pdf$'
    if not re.match(pattern, filename, re.IGNORECASE):
        return jsonify({'error': '无效的文件名'}), 400

    pdf_path = os.path.join(app.config['PDF_FOLDER'], filename)

    # 验证路径在预期目录内
    real_path = os.path.realpath(pdf_path)
    if not real_path.startswith(os.path.realpath(app.config['PDF_FOLDER'])):
        return jsonify({'error': '非法路径'}), 400

    if not os.path.exists(pdf_path):
        return jsonify({'error': 'PDF不存在'}), 404

    return send_file(pdf_path, as_attachment=True, download_name='images.pdf')


if __name__ == '__main__':
    # 生产环境应使用 gunicorn 或 waitress
    app.run(host='0.0.0.0', port=5000, debug=False)