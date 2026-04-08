// 图片转PDF - 前端逻辑

let sessionId = null;
let uploadedFiles = [];
let sortable = null;
let currentModalIndex = -1;
const MAX_FILES = 50; // 最大文件数

// DOM元素
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const imagesSection = document.getElementById('imagesSection');
const imageGrid = document.getElementById('imageGrid');
const clearBtn = document.getElementById('clearBtn');
const generateBtn = document.getElementById('generateBtn');
const loading = document.getElementById('loading');
const imageModal = document.getElementById('imageModal');
const modalImage = document.getElementById('modalImage');
const modalInfo = document.getElementById('modalInfo');
const modalClose = document.getElementById('modalClose');
const modalPrev = document.getElementById('modalPrev');
const modalNext = document.getElementById('modalNext');
const addMoreBtn = document.getElementById('addMoreBtn');
const imageCount = document.getElementById('imageCount');

// 初始化
function init() {
    // 点击上传
    uploadArea.addEventListener('click', () => fileInput.click());

    // 文件选择
    fileInput.addEventListener('change', handleFileSelect);

    // 添加更多按钮
    if (addMoreBtn) {
        addMoreBtn.addEventListener('click', () => fileInput.click());
    }

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

    // 模态框事件
    modalClose.addEventListener('click', closeModal);
    imageModal.addEventListener('click', (e) => {
        if (e.target === imageModal) closeModal();
    });
    modalPrev.addEventListener('click', showPrevImage);
    modalNext.addEventListener('click', showNextImage);

    // 键盘事件
    document.addEventListener('keydown', (e) => {
        if (!imageModal.classList.contains('active')) return;
        if (e.key === 'Escape') closeModal();
        if (e.key === 'ArrowLeft') showPrevImage();
        if (e.key === 'ArrowRight') showNextImage();
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
    // 检查总数限制
    const totalFiles = uploadedFiles.length + files.length;
    if (totalFiles > MAX_FILES) {
        alert(`最多只能上传${MAX_FILES}张图片，当前已上传${uploadedFiles.length}张`);
        return;
    }

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
            // 追加新文件到现有列表，而不是替换
            uploadedFiles = [...uploadedFiles, ...result.files];
            renderImages();
            imagesSection.style.display = 'block';
            updateImageCount();
            // 隐藏上传区域，显示添加按钮
            uploadArea.style.display = 'none';
            if (addMoreBtn) addMoreBtn.style.display = 'inline-flex';
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

        // 使用缩略图预览
        item.innerHTML = `
            <img src="${file.thumbnail}" alt="${file.filename}" loading="lazy">
            <button class="delete-btn" onclick="event.stopPropagation(); deleteImage('${file.id}')">×</button>
            <span class="order-number">${index + 1}</span>
        `;

        imageGrid.appendChild(item);
    });

    // 绑定点击事件（使用事件委托）
    imageGrid.querySelectorAll('.image-item').forEach(item => {
        item.addEventListener('click', (e) => {
            if (!e.target.classList.contains('delete-btn')) {
                openModalByElement(item);
            }
        });
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

// 获取当前 DOM 顺序的文件列表
function getOrderedFiles() {
    const items = Array.from(imageGrid.querySelectorAll('.image-item'));
    return items.map(item => {
        return uploadedFiles.find(f => f.id === item.dataset.id);
    }).filter(f => f);
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
            updateImageCount();

            if (uploadedFiles.length === 0) {
                imagesSection.style.display = 'none';
                uploadArea.style.display = 'block';
                if (addMoreBtn) addMoreBtn.style.display = 'none';
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
            sessionId = null;
            imageGrid.innerHTML = '';
            imagesSection.style.display = 'none';
            uploadArea.style.display = 'block';
            if (addMoreBtn) addMoreBtn.style.display = 'none';
        } else {
            alert('清空失败: ' + result.error);
        }
    } catch (error) {
        alert('清空失败: ' + error.message);
    }
}

// 更新图片数量显示
function updateImageCount() {
    if (imageCount) {
        imageCount.textContent = `${uploadedFiles.length}/${MAX_FILES}`;
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

// 模态框功能
function openModalByElement(clickedItem) {
    const items = Array.from(imageGrid.querySelectorAll('.image-item'));
    const orderedFiles = getOrderedFiles();

    // 找到被点击元素在当前 DOM 中的索引
    currentModalIndex = items.indexOf(clickedItem);
    const file = orderedFiles[currentModalIndex];

    if (!file) return;

    modalImage.src = file.path;
    modalInfo.textContent = `${file.filename} (${file.width} × ${file.height})`;
    imageModal.classList.add('active');

    // 更新导航按钮状态
    updateModalNavButtons(orderedFiles.length);
}

function closeModal() {
    imageModal.classList.remove('active');
    currentModalIndex = -1;
}

function showPrevImage() {
    const orderedFiles = getOrderedFiles();
    const total = orderedFiles.length;

    if (total <= 1) return;

    if (currentModalIndex > 0) {
        currentModalIndex--;
    } else {
        currentModalIndex = total - 1; // 循环到最后一张
    }

    const file = orderedFiles[currentModalIndex];
    modalImage.src = file.path;
    modalInfo.textContent = `${file.filename} (${file.width} × ${file.height})`;
}

function showNextImage() {
    const orderedFiles = getOrderedFiles();
    const total = orderedFiles.length;

    if (total <= 1) return;

    if (currentModalIndex < total - 1) {
        currentModalIndex++;
    } else {
        currentModalIndex = 0; // 循环到第一张
    }

    const file = orderedFiles[currentModalIndex];
    modalImage.src = file.path;
    modalInfo.textContent = `${file.filename} (${file.width} × ${file.height})`;
}

function updateModalNavButtons(total) {
    modalPrev.style.display = total > 1 ? 'flex' : 'none';
    modalNext.style.display = total > 1 ? 'flex' : 'none';
}

// 启动
init();