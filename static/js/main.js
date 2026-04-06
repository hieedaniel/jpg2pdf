// 图片转PDF - 前端逻辑

let sessionId = null;
let uploadedFiles = [];
let sortable = null;

// DOM元素
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const imagesSection = document.getElementById('imagesSection');
const imageGrid = document.getElementById('imageGrid');
const clearBtn = document.getElementById('clearBtn');
const generateBtn = document.getElementById('generateBtn');
const loading = document.getElementById('loading');

// 初始化
function init() {
    // 点击上传
    uploadArea.addEventListener('click', () => fileInput.click());

    // 文件选择
    fileInput.addEventListener('change', handleFileSelect);

    // 拖拽上传
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            uploadFiles(files);
        }
    });

    // 清空按钮
    clearBtn.addEventListener('click', clearAll);

    // 生成PDF按钮
    generateBtn.addEventListener('click', generatePDF);

    // 初始化拖拽排序
    sortable = new Sortable(imageGrid, {
        animation: 150,
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        onEnd: updateOrderNumbers
    });
}

// 文件选择处理
function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        uploadFiles(files);
    }
    fileInput.value = ''; // 清空，允许重复选择相同文件
}

// 上传文件
async function uploadFiles(files) {
    showLoading(true);

    const formData = new FormData();
    formData.append('session_id', sessionId || '');

    for (const file of files) {
        formData.append('files', file);
    }

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            sessionId = result.session_id;
            uploadedFiles = result.files;
            renderImages();
            imagesSection.style.display = 'block';
        } else {
            alert('上传失败: ' + result.error);
        }
    } catch (error) {
        alert('上传失败: ' + error.message);
    }

    showLoading(false);
}

// 渲染图片列表
function renderImages() {
    imageGrid.innerHTML = '';

    uploadedFiles.forEach((file, index) => {
        const item = document.createElement('div');
        item.className = 'image-item';
        item.dataset.id = file.id;

        item.innerHTML = `
            <img src="${file.path}" alt="${file.filename}">
            <button class="delete-btn" onclick="deleteImage('${file.id}')">×</button>
            <span class="order-number">${index + 1}</span>
        `;

        imageGrid.appendChild(item);
    });

    updateOrderNumbers();
}

// 更新序号
function updateOrderNumbers() {
    const items = imageGrid.querySelectorAll('.image-item');
    items.forEach((item, index) => {
        const orderSpan = item.querySelector('.order-number');
        if (orderSpan) {
            orderSpan.textContent = index + 1;
        }
    });

    // 更新uploadedFiles数组顺序
    const newOrder = [];
    items.forEach(item => {
        const id = item.dataset.id;
        const file = uploadedFiles.find(f => f.id === id);
        if (file) {
            newOrder.push(file);
        }
    });
    uploadedFiles = newOrder;
}

// 删除单个图片
async function deleteImage(fileId) {
    try {
        const response = await fetch('/delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: sessionId,
                file_id: fileId
            })
        });

        const result = await response.json();

        if (result.success) {
            uploadedFiles = uploadedFiles.filter(f => f.id !== fileId);
            renderImages();

            if (uploadedFiles.length === 0) {
                imagesSection.style.display = 'none';
            }
        } else {
            alert('删除失败: ' + result.error);
        }
    } catch (error) {
        alert('删除失败: ' + error.message);
    }
}

// 清空所有图片
async function clearAll() {
    if (!sessionId) return;

    if (!confirm('确定清空所有图片？')) return;

    try {
        const response = await fetch('/clear', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: sessionId
            })
        });

        const result = await response.json();

        if (result.success) {
            uploadedFiles = [];
            imageGrid.innerHTML = '';
            imagesSection.style.display = 'none';
        } else {
            alert('清空失败: ' + result.error);
        }
    } catch (error) {
        alert('清空失败: ' + error.message);
    }
}

// 生成PDF
async function generatePDF() {
    if (!sessionId || uploadedFiles.length === 0) {
        alert('请先上传图片');
        return;
    }

    showLoading(true);

    // 获取当前排序
    const fileOrder = Array.from(imageGrid.querySelectorAll('.image-item'))
        .map(item => item.dataset.id);

    try {
        const response = await fetch('/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: sessionId,
                file_order: fileOrder
            })
        });

        const result = await response.json();

        if (result.success) {
            // 下载PDF
            window.location.href = result.pdf_url;
        } else {
            alert('生成失败: ' + result.error);
        }
    } catch (error) {
        alert('生成失败: ' + error.message);
    }

    showLoading(false);
}

// 显示/隐藏加载状态
function showLoading(show) {
    loading.style.display = show ? 'block' : 'none';
    generateBtn.disabled = show;
    clearBtn.disabled = show;
}

// 启动
init();