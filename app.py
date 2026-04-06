#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JPG2PDF Web应用 - Flask后端
支持上传图片、排序、生成PDF
"""

import os
import uuid
import time
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
import img2pdf
from PIL import Image

app = Flask(__name__)

# 配置
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
PDF_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'pdfs')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'bmp', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB最大上传

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PDF_FOLDER'] = PDF_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 确保目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    """上传图片"""
    files = request.files.getlist('files')

    if not files:
        return jsonify({'error': '没有选择文件'}), 400

    uploaded_files = []
    session_id = request.form.get('session_id') or str(uuid.uuid4())

    # 创建会话目录
    session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    os.makedirs(session_folder, exist_ok=True)

    for file in files:
        if file and allowed_file(file.filename):
            # 使用UUID作为文件名，保留原始扩展名
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_name = f"{uuid.uuid4()}.{ext}"
            filepath = os.path.join(session_folder, unique_name)

            file.save(filepath)

            # 获取图片尺寸
            try:
                with Image.open(filepath) as img:
                    width, height = img.size
            except:
                width, height = 0, 0

            uploaded_files.append({
                'id': unique_name,
                'filename': file.filename,
                'path': f'/static/uploads/{session_id}/{unique_name}',
                'width': width,
                'height': height
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

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], session_id, file_id)

    if os.path.exists(filepath):
        try:
            os.remove(filepath)
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

    session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)

    if os.path.exists(session_folder):
        try:
            for filename in os.listdir(session_folder):
                filepath = os.path.join(session_folder, filename)
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

    session_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)

    # 检查所有文件是否存在
    image_paths = []
    for file_id in file_order:
        filepath = os.path.join(session_folder, file_id)
        if os.path.exists(filepath):
            image_paths.append(filepath)
        else:
            return jsonify({'error': f'文件不存在: {file_id}'}), 404

    if not image_paths:
        return jsonify({'error': '没有图片'}), 400

    # 生成PDF
    pdf_filename = f"{session_id}.pdf"
    pdf_path = os.path.join(app.config['PDF_FOLDER'], pdf_filename)

    try:
        with open(pdf_path, 'wb') as f:
            f.write(img2pdf.convert(image_paths))
    except Exception as e:
        return jsonify({'error': f'生成PDF失败: {str(e)}'}), 500

    return jsonify({
        'success': True,
        'pdf_url': f'/download/{pdf_filename}'
    })


@app.route('/download/<filename>')
def download(filename):
    """下载PDF"""
    pdf_path = os.path.join(app.config['PDF_FOLDER'], filename)

    if not os.path.exists(pdf_path):
        return jsonify({'error': 'PDF不存在'}), 404

    return send_file(pdf_path, as_attachment=True, download_name='images.pdf')


if __name__ == '__main__':
    # 生产环境应使用 gunicorn 或 waitress
    app.run(host='0.0.0.0', port=5000, debug=False)